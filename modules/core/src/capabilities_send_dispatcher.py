"""Capabilities: send button dispatcher (AES403).

Implements ISendProtocol.
"""

from __future__ import annotations

import contextlib
import time
from typing import Any, cast

from playwright.sync_api import Error, Page

from modules.core.src.utility_core_dom_helper import click_send as _dom_click_send
from modules.core.src.utility_core_dom_query import count_messages, latest_message_text
from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src.contract_core_protocol import ISendProtocol
from modules.shared.src.taxonomy_config_vo import SenderConfig
from modules.shared.src.taxonomy_core_constant import SEND_DISABLED_SELECTORS, TEXTAREA_SELECTOR
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_error import SendDispatchError
from modules.shared.src.taxonomy_core_event import EVENT_DISPATCH_ACKNOWLEDGED, EVENT_SEND_CLICKED
from modules.shared.src.taxonomy_core_vo import (
    ClickTimeoutMs,
    MessageCount,
    ResponseText,
    TryEnterKeyFallbackFlag,
)

log = get_logger("capabilities_send_dispatcher")


def _is_parse_toast_visible(page: Page) -> bool:
    """Safely check if Qwen's document parsing warning toast is visible."""
    try:
        toast = page.locator("body").filter(
            has_text="Please wait until the uploaded or currently parsing file"
        )
        c = toast.count()
        if isinstance(c, int) and c > 0:
            return bool(toast.first.is_visible(timeout=100))
    except Exception:
        pass
    return False


def _is_file_card_parsing(page: Page) -> bool:
    """Return True if any file card in the composer input area still shows a Parsing indicator.

    Checks proactively (before clicking send) so the dispatcher never races against
    Qwen's backend document-parsing stage.
    """
    for sel in (
        ".message-input-column-file",
        ".file-card-list",
        "[class*='fileitem-btn']",
        "[class*='fileitem']",
    ):
        try:
            loc = page.locator(sel)
            c = loc.count()
            if not isinstance(c, int) or c == 0:
                continue
            for i in range(min(c, 5)):
                text = loc.nth(i).inner_text(timeout=200).casefold()
                if "parsing" in text or "processing" in text:
                    return True
        except Exception:
            pass
    return False


# Block 1: Class Definition & Constructor


class SendDispatcher(ISendProtocol):
    """Multi-strategy send button trigger with keyboard fallback."""

    def __init__(
        self,
        click_timeout_ms: ClickTimeoutMs = ClickTimeoutMs(10000),
        try_enter_key_fallback: TryEnterKeyFallbackFlag = TryEnterKeyFallbackFlag(True),
    ) -> None:
        self.click_timeout_ms = click_timeout_ms
        self.try_enter_key_fallback = try_enter_key_fallback

    # ─── Block 2: Public Contract (ISendProtocol ONLY) ──
    def click_send(
        self,
        page: Page,
        emitter: LifecycleEmitter,
        _config: SenderConfig | None = None,
        document_parsed: bool = True,
    ) -> None:
        """Click the prompt send button using verified selectors with keyboard Enter fallback."""
        if not document_parsed:
            raise SendDispatchError(
                "Cannot send prompt: document attachment parsing (EVENT_DOCUMENT_PARSED) is incomplete"
            )

        effective_config = _config or SenderConfig(
            click_timeout_ms=int(self.click_timeout_ms),
            try_enter_key_fallback=bool(self.try_enter_key_fallback),
        )

        deadline = time.monotonic() + (effective_config.click_timeout_ms / 1000)
        while time.monotonic() < deadline:
            self._wait_for_send_enabled(page, timeout_ms=effective_config.click_timeout_ms)
            baseline_count = int(count_messages(page))
            if not _dom_click_send(page, _config=effective_config):
                raise SendDispatchError("Unable to dispatch prompt: send button and Enter fallback both failed")

            page.wait_for_timeout(300)
            if _is_parse_toast_visible(page):
                log.info("Document parsing is still in progress (Qwen toast displayed). Waiting for completion...")
                page.wait_for_timeout(1000)
                continue

            details: dict[str, object] = {"selector": "SendDispatcher"}
            emitter.emit(EVENT_SEND_CLICKED, details)
            if not self._wait_for_dispatch_ack(page, baseline_count):
                if _is_parse_toast_visible(page):
                    page.wait_for_timeout(1000)
                    continue
                try:
                    textarea = page.locator(TEXTAREA_SELECTOR).first
                    textarea.press("Enter")
                except (Error, TimeoutError):
                    with contextlib.suppress(Error, TimeoutError):
                        page.keyboard.press("Enter")
                if not self._wait_for_dispatch_ack(page, baseline_count):
                    if _is_parse_toast_visible(page):
                        page.wait_for_timeout(1000)
                        continue
                    raise SendDispatchError("Send control was clicked but Qwen did not acknowledge the user turn")
            emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, details)
            return

        raise SendDispatchError("Send control dispatch timed out waiting for document parsing or user turn ACK")

    def _wait_for_dispatch_ack(self, page: Page, baseline_count: int) -> bool:
        """Verify that the click produced a new user turn or reset the composer."""
        from modules.core.src.utility_core_dom_query import latest_message_text as _latest_message_text

        deadline = time.monotonic() + (self.click_timeout_ms / 1000)
        baseline_text = _latest_message_text(page)
        while time.monotonic() < deadline:
            try:
                if int(count_messages(page)) > baseline_count:
                    return True
                textarea = page.locator(TEXTAREA_SELECTOR).first
                textarea_count = cast(Any, textarea.count())
                if not isinstance(textarea_count, int):
                    return True
                if textarea_count > 0:
                    value = textarea.input_value(timeout=100)
                    if not value.strip():
                        return True
                disabled_count = cast(Any, page.locator(SEND_DISABLED_SELECTORS).count())
                if isinstance(disabled_count, int) and disabled_count > 0:
                    return True
                current_text = _latest_message_text(page)
                if current_text != baseline_text and current_text is not None:
                    return True
            except (Error, TimeoutError):
                pass
            page.wait_for_timeout(100)
        return False

    def _wait_for_send_enabled(self, page: Page, timeout_ms: int = 5000) -> None:
        """Wait until send is safe: no file parsing in progress AND button is enabled."""
        deadline = time.monotonic() + (timeout_ms / 1000)
        while time.monotonic() < deadline:
            try:
                # Proactive check: file card still shows "Parsing..." in DOM
                if _is_file_card_parsing(page):
                    log.debug("File card still parsing — holding send.")
                    page.wait_for_timeout(500)
                    continue

                # Reactive check: toast appeared after a premature click attempt
                if _is_parse_toast_visible(page):
                    log.debug("Parse toast visible — holding send.")
                    page.wait_for_timeout(500)
                    continue

                for selector in (
                    ".message-input-right-button-send button:not([disabled]):not(.disabled)",
                    "button.send-button:not([disabled]):not(.disabled)",
                    "button[aria-label*='Send' i]:not([disabled]):not(.disabled)",
                    "button[type='submit']:not([disabled]):not(.disabled)",
                    "button[class*='send' i]:not([disabled]):not(.disabled)",
                ):
                    loc = page.locator(selector).first
                    c = loc.count()
                    if isinstance(c, int) and c > 0 and loc.is_visible(timeout=100) and loc.is_enabled(timeout=100):
                        return
            except (Error, TimeoutError):
                pass
            page.wait_for_timeout(200)

    def count_messages(self, page: Page) -> MessageCount:
        """Count chat turns using JS evaluate."""
        return count_messages(page)

    def latest_message_text(self, page: Page) -> ResponseText | None:
        """Get the longest text block on page excluding input/UI chrome."""
        return latest_message_text(page)

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def __repr__(self) -> str:
        """Return string representation of SendDispatcher."""
        return f"SendDispatcher(timeout={self.click_timeout_ms}, fallback={self.try_enter_key_fallback})"
