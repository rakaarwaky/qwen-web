"""Capabilities: send button dispatcher (AES403).

Implements ISendProtocol.
"""

from __future__ import annotations

from playwright.sync_api import Page

from modules.core.src.utility_core_dom_helper import click_send as _dom_click_send
from modules.core.src.utility_core_dom_query import count_messages, latest_message_text
from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_SEND_CLICKED,
    ClickTimeoutMs,
    ISendProtocol,
    LifecycleEmitter,
    MessageCount,
    ResponseText,
    SendDispatchError,
    SenderConfig,
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
        if not _dom_click_send(page, _config=effective_config):
            raise SendDispatchError("Unable to dispatch prompt: send button and Enter fallback both failed")
        details: dict[str, object] = {"selector": "SendDispatcher"}
        emitter.emit(EVENT_SEND_CLICKED, details)
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, details)

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
