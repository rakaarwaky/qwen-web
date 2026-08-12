"""Qwen Web client facade — delegates to feature modules.

External API unchanged: QwenClient(ctx, cfg), .send_file(), .reset_page(), .start(), .stop()
"""
from __future__ import annotations

import threading
import types
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, ElementHandle, Locator, Page

from .browser import (
    SessionCheck,
    navigate_to_chat,
)
from .browser import (
    check_auth as _check_auth,
)
from .browser import (
    reset_page as _reset_page,
)
from .file_uploader import upload_attachment
from .observability import get_logger
from .prompt_injector import find_input, inject_text
from .prompt_injector import type_slowly as _type_slowly_mod
from .sender import click_send, count_messages, latest_message_text
from .streamer import wait_for_response
from .types import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_DOCUMENT_PARSED,
    EVENT_OUTPUT_COPIED,
    EVENT_PROMPT_INJECTED,
    EVENT_SEND_CLICKED,
    AppConfig,
    LifecycleEmitter,
    QwenCliError,
    SendDispatchError,
)

log = get_logger("qwen_client")

# Re-export for backward compat (tests import SessionCheck from here)
__all__ = ["QwenClient", "SessionCheck"]


class QwenClient:
    """Wraps a Playwright persistent context to interact with chat.qwen.ai."""

    def __init__(
        self,
        ctx: BrowserContext | None,
        cfg: AppConfig | None = None,
        emitter: LifecycleEmitter | None = None,
    ) -> None:
        """Initialize QwenClient with browser context, config, and event emitter."""
        self.cfg = cfg
        self.browser: Browser | None = None
        self.context: BrowserContext | None = ctx
        self.page: Page | None = ctx.pages[0] if ctx and ctx.pages else (ctx.new_page() if ctx else None)
        self.emitter: LifecycleEmitter = emitter or LifecycleEmitter()

    def start(self) -> None:
        """No-op — browser context is managed externally via browser_session()."""

    def stop(self) -> None:
        """No-op — browser context is managed externally via browser_session()."""

    def reset_page(self) -> None:
        """Reset the page to a clean state."""
        if self.page:
            _reset_page(self.page, self.emitter)

    def send_file(self, filepath: Path, timeout_sec: int, custom_prompt_path: Path | None = None, rel_path: Path | None = None) -> str:
        """Send a prompt file to chat.qwen.ai and return the full AI response as text."""
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            prompt = filepath.read_text(encoding="utf-8").strip()
        except OSError as e:
            raise QwenCliError(f"Failed to read prompt file {filepath}: {e}") from e

        from .pipeline import load_role_prompt
        role_prompt = load_role_prompt(filepath, custom_prompt_path, rel_path)
        if role_prompt:
            prompt = f"{role_prompt}\n\n{prompt}"

        navigate_to_chat(self.page, self.emitter)
        _check_auth(self.page)

        log.info("Sending prompt to chat.qwen.ai (%d chars)", len(prompt))
        msg_count_before = count_messages(self.page)

        # Pure Event-Driven State Machine Variables
        document_parsed_event = threading.Event()
        prompt_injected_event = threading.Event()
        send_clicked_event = threading.Event()
        execution_error: list[Exception] = []

        # Event Handler 1: When DOCUMENT_PARSED is emitted, reactively trigger prompt injection
        def _on_document_parsed(data: dict[str, Any]) -> None:
            log.info("[EDD Reactive] Handling EVENT_DOCUMENT_PARSED -> Triggering Prompt Injection")
            document_parsed_event.set()
            try:
                text_to_inject = role_prompt if role_prompt else f"Please analyze and complete the task described in the attached file: {filepath.name}"
                inject_text(self.page, text_to_inject, emitter=self.emitter)
            except Exception as exc:
                execution_error.append(exc)

        # Event Handler 2: When PROMPT_INJECTED is emitted, reactively trigger click_send
        def _on_prompt_injected(data: dict[str, Any]) -> None:
            log.info("[EDD Reactive] Handling EVENT_PROMPT_INJECTED -> Triggering Click Send")
            prompt_injected_event.set()
            try:
                click_send(self.page, self.emitter, document_parsed=document_parsed_event.is_set(), prompt_injected=True)
            except Exception as exc:
                execution_error.append(exc)

        # Event Handler 3: When SEND_CLICKED is emitted, set send_clicked_event flag
        def _on_send_clicked(data: dict[str, Any]) -> None:
            log.info("[EDD Reactive] Handling EVENT_SEND_CLICKED -> Dispatch Confirmed")
            send_clicked_event.set()

        # Register Reactive Event Listeners
        self.emitter.on(EVENT_DOCUMENT_PARSED, _on_document_parsed)
        self.emitter.on(EVENT_PROMPT_INJECTED, _on_prompt_injected)
        self.emitter.on(EVENT_SEND_CLICKED, _on_send_clicked)

        try:
            # Entry Event Trigger: Start attachment upload
            find_input(self.page)
            attached = upload_attachment(self.page, filepath, emitter=self.emitter, web_loaded=True)

            if not attached:
                log.warning("File upload failed, proceeding with text-only prompt: %s", filepath.name)
                # Emit EVENT_DOCUMENT_PARSED manually for text-only fallback to trigger reactive chain
                self.emitter.emit(EVENT_DOCUMENT_PARSED, {"file": str(filepath), "char_count": len(prompt)})

            # Wait for reactive event-driven dispatch sequence to complete
            if not send_clicked_event.wait(timeout=60.0):
                if execution_error:
                    raise execution_error[0]
                raise SendDispatchError("Event-driven dispatch chain timed out waiting for EVENT_SEND_CLICKED")

            if execution_error:
                raise execution_error[0]

            self.emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, {"file": str(filepath)})
            response = self._wait_for_response(timeout_sec, msg_count_before)

            if response and len(response.strip()) > 0:
                log.info("Received response (%d chars)", len(response))
                self.emitter.emit(EVENT_OUTPUT_COPIED, {"file": str(filepath), "char_count": len(response.strip())})
                return response.strip()
            else:
                raise TimeoutError(f"Timeout after {timeout_sec}s: no response detected")
        finally:
            # Clean up temporary reactive listeners
            self.emitter.off(EVENT_DOCUMENT_PARSED, _on_document_parsed)
            self.emitter.off(EVENT_PROMPT_INJECTED, _on_prompt_injected)
            self.emitter.off(EVENT_SEND_CLICKED, _on_send_clicked)

    # ─── Backward-compat delegates (tests call these directly) ───────────────
    def _type_slowly(self, textarea: ElementHandle | Locator, text: str, delay_ms: int = 30) -> None:
        if self.page and isinstance(textarea, ElementHandle):
            _type_slowly_mod(self.page, textarea, text, delay_ms)

    def _count_messages(self) -> int:
        return count_messages(self.page) if self.page else 0

    def _latest_message_text(self) -> str | None:
        return latest_message_text(self.page) if self.page else None

    def _wait_for_response(self, timeout_sec: int, msg_count_before: int, dispatch_acknowledged: bool = True) -> str | None:
        return wait_for_response(self.page, timeout_sec, msg_count_before, self.emitter, dispatch_acknowledged=dispatch_acknowledged) if self.page else None

    def __enter__(self) -> QwenClient:
        """Enter the context manager and start the client."""
        self.start()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None) -> None:
        """Exit the context manager and stop the client."""
        self.stop()
