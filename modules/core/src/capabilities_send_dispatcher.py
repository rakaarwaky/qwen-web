"""Capabilities: send button dispatcher (AES403).

Implements ISendProtocol.
"""

from __future__ import annotations

from playwright.sync_api import Error, Page

from modules.shared.src.contract_core_protocol import ISendProtocol
from modules.shared.src.taxonomy_config_vo import SenderConfig
from modules.shared.src.taxonomy_core_constant import MESSAGE_SELECTORS, SEND_SELECTORS, TEXTAREA_SELECTOR
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_vo import (
    EVENT_SEND_CLICKED,
    ClickTimeoutMs,
    MessageCount,
    ResponseText,
    TryEnterKeyFallbackFlag,
)
from modules.shared.src.taxonomy_domain_error import SendDispatchError
from modules.core.src.utility_core_dom_query import click_send as _dom_click_send

log = __import__("logging").getLogger("capabilities_send_dispatcher")


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
        config: SenderConfig | None = None,
        document_parsed: bool = True,
    ) -> None:
        """Click the prompt send button using verified selectors with keyboard Enter fallback."""
        if not document_parsed:
            raise SendDispatchError(
                "Cannot send prompt: document attachment parsing (EVENT_DOCUMENT_PARSED) is incomplete"
            )

        _dom_click_send(page)
        emitter.emit(EVENT_SEND_CLICKED, {"selector": "SendDispatcher"})

    def count_messages(self, page: Page) -> MessageCount:
        """Count chat turns using JS evaluate."""
        try:
            count = page.evaluate(
                """() => {
                    var turns = document.querySelectorAll(
                        '[class*="chat-message"]', '[class*="message-item"]', '[class*="virtual-list-item"]', '[class*="turn"]'
                    );
                    return turns.length;
                }"""
            )
            if isinstance(count, int) and count > 0:
                return MessageCount(count)
        except Error:
            pass
        try:
            combined = ", ".join(MESSAGE_SELECTORS)
            return MessageCount(page.locator(combined).count())
        except Error:
            return MessageCount(0)

    def latest_message_text(self, page: Page) -> ResponseText | None:
        """Get the longest text block on page excluding input/UI chrome."""
        try:
            text = page.evaluate(
                """() => {
                    var containers = ['#chatLog', '[class*="chat-log"]', '[class*="virtual-list"]',
                                      '[class*="message-list"]', '[class*="conversation-body"]',
                                      '[class*="dialog-content"]'];
                    for (var ci = 0; ci < containers.length; ci++) {
                        var container = document.querySelector(containers[ci]);
                        if (container && container.children.length > 0) {
                            var lastChild = container.children[container.children.length - 1];
                            var txt = (lastChild.innerText || '').trim();
                            if (txt.length > 20) return txt;
                        }
                    }
                    var SKIP_CLASSES = [
                        'model-selector', 'fileitem', 'placeholder', 'message-input',
                        'header', 'footer', 'feedback', 'downLoad', 'sidebar',
                        'mode-select', 'send-button', 'toolbar', 'nav', 'spinner',
                        'thinking', 'attachment', 'file-card', 'file-content',
                        'chat-footer', 'chat-prompt-recommend'
                    ];
                    function isInChrome(el) {
                        var p = el;
                        while (p) {
                            var cls = p.className;
                            if (cls && typeof cls === 'string') {
                                for (var i = 0; i < SKIP_CLASSES.length; i++) {
                                    if (cls.indexOf(SKIP_CLASSES[i]) >= 0) return true;
                                }
                            }
                            if (p.tagName === 'HEADER' || p.tagName === 'FOOTER' ||
                                p.tagName === 'NAV' || p.tagName === 'ASIDE') return true;
                            p = p.parentElement;
                        }
                        return false;
                    }
                    var best = null;
                    var bestLen = 0;
                    var all = document.querySelectorAll('div, p, pre, section, article, main');
                    for (var i = 0; i < all.length; i++) {
                        var el = all[i];
                        if (['SCRIPT','STYLE','TEXTAREA','INPUT','BUTTON'].indexOf(el.tagName) >= 0) continue;
                        if (isInChrome(el)) continue;
                        var txt2 = (el.innerText || '').trim();
                        if (txt2.length > bestLen) { bestLen = txt2.length; best = txt2; }
                    }
                    return best;
                }"""
            )
            if text and len(text.strip()) > 0:
                return ResponseText(str(text.strip()))
        except Error:
            pass
        try:
            combined = ", ".join(MESSAGE_SELECTORS)
            locator = page.locator(combined)
            if locator.count() > 0:
                text = locator.last.text_content()
                if text is not None:
                    return ResponseText(str(text.strip()))
        except Error:
            pass
        return None

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def __repr__(self) -> str:
        """Return string representation of SendDispatcher."""
        return f"SendDispatcher(timeout={self.click_timeout_ms}, fallback={self.try_enter_key_fallback})"
