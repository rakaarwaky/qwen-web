"""Qwen Web client facade — delegates to feature modules.

External API unchanged: QwenClient(ctx, cfg), .send_file(), .reset_page(), .start(), .stop()
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import BrowserContext, Page

from .types import (
    AppConfig,
    LifecycleEmitter,
    EVENT_DOCUMENT_PARSED,
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_OUTPUT_COPIED,
)
from .browser import (
    SessionCheck,
    reset_page as _reset_page,
    navigate_to_chat,
    check_auth as _check_auth,
)
from .file_uploader import upload_attachment
from .prompt_injector import find_input, inject_text, type_slowly
from .sender import click_send, count_messages, latest_message_text
from .streamer import wait_for_response
from .prompt_injector import type_slowly as _type_slowly_mod
from .observability import get_logger

log = get_logger("qwen_client")

# Re-export for backward compat (tests import SessionCheck from here)
__all__ = ["QwenClient", "SessionCheck"]


class QwenClient:
    """Wraps a Playwright persistent context to interact with chat.qwen.ai."""

    def __init__(
        self,
        ctx: BrowserContext | None,
        cfg: AppConfig | None = None,
        emitter: Optional[LifecycleEmitter] = None,
    ) -> None:
        self.cfg = cfg
        self.browser: Browser | None = None
        self.context: BrowserContext | None = ctx
        self.page: Page | None = ctx.pages[0] if ctx and ctx.pages else (ctx.new_page() if ctx else None)
        self.emitter: LifecycleEmitter = emitter or LifecycleEmitter()

    def start(self) -> None:
        """No-op — browser context is managed externally via browser_session()."""
        pass

    def stop(self) -> None:
        """No-op — browser context is managed externally via browser_session()."""
        pass

    def reset_page(self) -> None:
        """Resets the page to a clean state."""
        if self.page:
            _reset_page(self.page, self.emitter)

    def send_file(self, filepath: Path, timeout_sec: int, custom_prompt_path: Optional[Path] = None, rel_path: Optional[Path] = None) -> str:
        """Sends a prompt file to chat.qwen.ai and returns the full AI response as text."""
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        prompt = filepath.read_text(encoding="utf-8").strip()

        if custom_prompt_path and custom_prompt_path.exists():
            role_prompt = custom_prompt_path.read_text(encoding="utf-8").strip()
            if role_prompt.startswith("---"):
                parts = role_prompt.split("---", 2)
                if len(parts) >= 3:
                    role_prompt = parts[2].strip()
            prompt = f"{role_prompt}\n\n{prompt}"

        navigate_to_chat(self.page, self.emitter)
        _check_auth(self.page)

        log.info("Sending prompt to chat.qwen.ai (%d chars)", len(prompt))
        msg_count_before = count_messages(self.page)

        find_input(self.page)
        upload_attachment(self.page, filepath)
        inject_text(self.page, prompt)
        self.emitter.emit(EVENT_DOCUMENT_PARSED, {"file": str(filepath), "char_count": len(prompt)})
        click_send(self.page, self.emitter)
        self.emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, {"file": str(filepath)})

        response = self._wait_for_response(timeout_sec, msg_count_before)

        if response and len(response.strip()) > 0:
            log.info("Received response (%d chars)", len(response))
            self.emitter.emit(EVENT_OUTPUT_COPIED, {"file": str(filepath), "char_count": len(response.strip())})
            return response.strip()
        else:
            raise TimeoutError(f"Timeout after {timeout_sec}s: no response detected")

    # ─── Backward-compat delegates (tests call these directly) ───────────────
    def _type_slowly(self, textarea: Any, text: str, delay_ms: float = 30) -> None:
        _type_slowly_mod(self.page, textarea, text, delay_ms)

    def _count_messages(self) -> int:
        return count_messages(self.page)

    def _latest_message_text(self) -> str | None:
        return latest_message_text(self.page)

    def _wait_for_response(self, timeout_sec: int, msg_count_before: int) -> str | None:
        return wait_for_response(self.page, timeout_sec, msg_count_before, self.emitter)

    _detect_response_mutation = _wait_for_response
    _adaptive_poll = _wait_for_response

    def __enter__(self) -> "QwenClient":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
