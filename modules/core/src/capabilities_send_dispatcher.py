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


# Block 1: Class Definition & Constructor


class SendDispatcher(ISendProtocol):
    """Multi-strategy send button trigger with keyboard fallback."""

    def __init__(
        self,
        click_timeout_ms: ClickTimeoutMs = ClickTimeoutMs(3000),
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
        baseline_count = int(count_messages(page))
        if not _dom_click_send(page, _config=effective_config):
            raise SendDispatchError("Unable to dispatch prompt: send button and Enter fallback both failed")
        details: dict[str, object] = {"selector": "SendDispatcher"}
        emitter.emit(EVENT_SEND_CLICKED, details)
        if not self._wait_for_dispatch_ack(page, baseline_count):
            try:
                textarea = page.locator(TEXTAREA_SELECTOR).first
                textarea.press("Enter")
            except (Error, TimeoutError):
                with contextlib.suppress(Error, TimeoutError):
                    page.keyboard.press("Enter")
            if not self._wait_for_dispatch_ack(page, baseline_count):
                raise SendDispatchError("Send control was clicked but Qwen did not acknowledge the user turn")
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, details)

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
