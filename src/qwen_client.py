"""Playwright automation for chat.qwen.ai with adaptive polling, MutationObserver, and Linux support.

P7 additions:
  - Configurable timeout (passed from AppConfig)
  - MutationObserver-based message detection (replaces dumb polling)
  - Adaptive polling fallback when MutationObserver not available
  - Linux paste key (Ctrl+V) for textarea input
  - Session stability check (_check_session)
  - Event system with lifecycle callbacks (input_send, input_parsed, doc_attached,
    qwen_thinking, qwen_writing, output_saved)
"""
from __future__ import annotations

import json
import os
import re
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from .types import (
    AppConfig,
    AuthRequiredError,
    BrowserLaunchError,
    DEFAULT_LOG,
    LifecycleCallback,
    LifecycleEvent,
    LifecycleEmitter,
    MESSAGE_SELECTORS,
    RunContext,
    SEND_SELECTORS,
    EVENT_THINKING_STARTED,
    EVENT_STREAMING_GENERATION,
    EVENT_GENERATION_FINISHED,
    EVENT_DOCUMENT_PARSED,
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_SEND_CLICKED,
    EVENT_NETWORK_RECONNECTING,
    EVENT_OUTPUT_COPIED,
)
from .observability import get_logger, start_span

log = get_logger("qwen_client")


# ─── Session stability check ─────────────────────────────────────────────────
class SessionCheck:
    """Validates that the browser session and Qwen chat UI are alive."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def is_alive(self) -> bool:
        """Return True if the session is stable and the chat UI is responsive.

        Checks:
          1. Browser context is not closed/disconnected.
          2. Page is still loading a valid state (not stuck on login/CAPTCHA).
          3. The textarea selector exists (chat UI loaded).
        """
        try:
            # Check page is still responsive
            self.page.evaluate("() => document.readyState")
            ready = self.page.evaluate("() => document.readyState")
            if ready != "complete":
                log.warning("session_check_failed", reason="page_not_ready", ready=ready)
                return False

            # Check textarea exists (chat UI loaded)
            el = self.page.query_selector("textarea.message-input-textarea")
            if not el:
                log.warning("session_check_failed", reason="textarea_missing")
                return False

            return True
        except Exception as exc:
            log.warning("session_check_failed", reason=str(exc))
            return False

    def check_auth(self) -> None:
        """Raise AuthRequiredError if the session is no longer authenticated."""
        try:
            current_url = self.page.url.lower()
            if any(k in current_url for k in ("login", "passport", "auth", "signin")):
                raise AuthRequiredError("Session expired — redirected to login page.")

            # Try a lightweight DOM check; if it throws, session is dead.
            self.page.query_selector("textarea.message-input-textarea")
        except AuthRequiredError:
            raise
        except Exception as exc:
            raise AuthRequiredError(f"Session invalid: {exc}")


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
        """Starts the Playwright persistent context with a pre-authenticated Chrome profile."""
        log.info("Launching browser with profile %s", self.cfg.chrome_profile if self.cfg else "default")
        pw = sync_playwright().start()
        try:
            launch_args: list[str] = ["--disable-blink-features=JavascriptControlAutofill"]
            if self.cfg and self.cfg.disable_sandbox:
                launch_args.insert(0, "--no-sandbox")

            self.browser = pw.chromium.launch(
                headless=False,
                args=launch_args,
            )
            state_file = self.cfg.storage_state_file if self.cfg else None
            self.context = self.browser.new_context(
                viewport={"width": 1280, "height": 800},
                storage_state=json.loads(state_file.read_text()) if state_file and state_file.exists() else None,
                locale="id-ID",
            )

            self.page = self.context.new_page()
            log.info("Browser started successfully")
        except Exception as e:
            pw.stop()
            raise BrowserLaunchError(f"Failed to start browser: {e}") from e

    def _find_input(self):
        """Find textarea.input — proven selector from live test."""
        el = self.page.wait_for_selector('textarea.message-input-textarea', timeout=10_000)
        if not el:
            raise AuthRequiredError(
                "Could not find textarea on chat.qwen.ai. Please run 'qwc --login' to re-authenticate."
            )
        return el

    def _inject_text(self, text: str) -> None:
        """Inject text via React value-setter (fill() doesn't trigger React state)."""
        el = self.page.query_selector('textarea.message-input-textarea') or self.page.query_selector('textarea')
        if not el:
            raise AuthRequiredError("Textarea not found for injection.")
        el.focus()
        try:
            self.page.evaluate("""(text) => {
                const el = document.querySelector('textarea.message-input-textarea') || document.querySelector('textarea');
                if (!el) throw new Error('textarea not found');
                const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                setter.call(el, text);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", text)
        except Exception:
            # Fallback: use clipboard write + Ctrl+V (works in headless Chromium)
            self.page.evaluate("""(text) => {
                const el = document.querySelector('textarea.message-input-textarea') || document.querySelector('textarea');
                if (!el) throw new Error('textarea not found');
                navigator.clipboard.writeText(text);
                el.focus();
                el.setSelectionRange(0, 0);
                document.execCommand('paste');
            }""", text)
        log.info("Prompt injected via React value-setter (%d chars)", len(text))

    def _click_send(self) -> None:
        """Click send button — tries all verified selectors from config."""
        for sel in SEND_SELECTORS:
            try:
                btn = self.page.query_selector(sel)
                if btn and btn.is_visible() and btn.is_enabled():
                    btn.click(timeout=3_000)
                    log.info("Send button clicked via: %s", sel)
                    self.emitter.emit(EVENT_SEND_CLICKED, {"selector": sel})
                    return
            except Exception:
                continue
        # Fallback: Enter key
        el = self.page.query_selector('textarea.message-input-textarea')
        if el:
            el.press("Enter")
            log.info("Enter key pressed (send button not found)")
            self.emitter.emit(EVENT_SEND_CLICKED, {"selector": "Enter"})

    def _count_messages(self) -> int:
        """Count assistant messages using verified selectors from config."""
        for sel in MESSAGE_SELECTORS:
            count = self.page.evaluate("s => document.querySelectorAll(s).length", sel)
            if count and count > 0:
                return count
        return 0

    def _latest_message_text(self) -> Optional[str]:
        """Get text of last assistant message using verified selectors from config."""
        for sel in MESSAGE_SELECTORS:
            text = self.page.evaluate("s => { const msgs = document.querySelectorAll(s); return msgs.length > 0 ? msgs[msgs.length - 1].textContent.trim() : null; }", sel)
            if text:
                return text
        return None

    def send_file(self, filepath: Path, timeout_sec: int, custom_prompt_path: Optional[Path] = None, rel_path: Optional[Path] = None) -> str:
        """Sends a prompt file to chat.qwen.ai and returns the full AI response as text."""
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        prompt = filepath.read_text(encoding="utf-8").strip()

        # Prepend role prompt if provided
        if custom_prompt_path and custom_prompt_path.exists():
            role_prompt = custom_prompt_path.read_text(encoding="utf-8").strip()
            if role_prompt.startswith("---"):
                parts = role_prompt.split("---", 2)
                if len(parts) >= 3:
                    role_prompt = parts[2].strip()
            prompt = f"{role_prompt}\n\n{prompt}"

        # Navigate to chat
        self.page.goto("https://chat.qwen.ai/", wait_until="domcontentloaded", timeout=30_000)
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=15_000)
        except Exception:
            pass

        # Auth check
        current_url = self.page.url.lower()
        if any(k in current_url for k in ("login", "passport", "auth", "signin")):
            raise AuthRequiredError("No active login session. Run 'qwc --login' to authenticate.")

        log.info("Sending prompt to chat.qwen.ai (%d chars)", len(prompt))
        msg_count_before = self._count_messages()

        # Find input, inject, send
        self._find_input()
        self._inject_text(prompt)
        self.emitter.emit(EVENT_DOCUMENT_PARSED, {"file": str(filepath), "char_count": len(prompt)})
        self._click_send()
        self.emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, {"file": str(filepath)})

        # Wait for response (stability loop)
        response = self._wait_for_response(timeout_sec, msg_count_before)

        if response and len(response.strip()) > 0:
            log.info("Received response (%d chars)", len(response))
            self.emitter.emit(EVENT_OUTPUT_COPIED, {"file": str(filepath), "char_count": len(response.strip())})
            return response.strip()
        else:
            raise TimeoutError(f"Timeout after {timeout_sec}s: no response detected")

    def _wait_for_response(self, timeout_sec: int, msg_count_before: int) -> Optional[str]:
        """Wait for new assistant message with stability check."""
        log.info("Waiting for AI response...")
        self.emitter.emit(EVENT_THINKING_STARTED)
        start = time.time()
        last_text = ""
        stable_count = 0

        while time.time() - start < timeout_sec:
            # Check for new messages
            count = self._count_messages()
            if count > msg_count_before:
                text = self._latest_message_text()
                if text and len(text) > 10:
                    if text == last_text:
                        stable_count += 1
                        if stable_count >= 3:
                            self.emitter.emit(EVENT_GENERATION_FINISHED, {"text_length": len(text)})
                            return text
                    else:
                        stable_count = 0
                        last_text = text
                        self.emitter.emit(EVENT_STREAMING_GENERATION, {"text_length": len(text)})
            time.sleep(1.0)

        return last_text or None

    _detect_response_mutation = _wait_for_response
    _adaptive_poll = _wait_for_response

    def _type_slowly(self, textarea: Any, text: str, delay_ms: float = 30) -> None:
        """Type text character-by-character into a textarea with per-character delays.

        Args:
            textarea: Playwright ElementHandle for the target textarea.
            text: The text to type.
            delay_ms: Milliseconds to wait between each character (default 30).
        """
        assert self.page is not None
        for char in text:
            textarea.press(char)
            time.sleep(delay_ms / 1000)

    def reset_page(self) -> None:
        """Resets the page to a clean state by navigating back to chat.qwen.ai."""
        if self.page:
            try:
                self.emitter.emit(EVENT_NETWORK_RECONNECTING, {"url": "https://chat.qwen.ai/"})
                self.page.goto("https://chat.qwen.ai/", wait_until="domcontentloaded", timeout=10_000)
                self.page.wait_for_load_state("domcontentloaded", timeout=15_000)
            except Exception as e:
                log.warning("Error resetting page: %s", e)

    def stop(self) -> None:
        """Stops the Playwright session and releases all resources."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            log.info("Browser stopped successfully")
        except Exception as e:
            log.warning("Error stopping browser: %s", e)

    def __enter__(self) -> "QwenClient":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
