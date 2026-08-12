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

log = __import__("logging").getLogger("capabilities_send_dispatcher")

DEFAULT_CLICK_TIMEOUT_MS = ClickTimeoutMs(3000)
DEFAULT_TRY_ENTER_KEY_FALLBACK = TryEnterKeyFallbackFlag(True)

COMBINED_MESSAGE_SELECTOR = ", ".join(MESSAGE_SELECTORS)

# JS for extracting response text from Qwen DOM
_JS_GET_RESPONSE_TEXT = """() => {
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

_JS_COUNT_TURNS = """() => {
    var turns = document.querySelectorAll(
        '[class*="chat-message"]', '[class*="message-item"]', '[class*="virtual-list-item"]', '[class*="turn"]'
    );
    return turns.length;
}"""


class SendDispatcher(ISendProtocol):
    """Multi-strategy send button trigger with keyboard fallback."""

    def __init__(
        self,
        click_timeout_ms: ClickTimeoutMs = DEFAULT_CLICK_TIMEOUT_MS,
        try_enter_key_fallback: TryEnterKeyFallbackFlag = DEFAULT_TRY_ENTER_KEY_FALLBACK,
    ) -> None:
        self.click_timeout_ms = click_timeout_ms
        self.try_enter_key_fallback = try_enter_key_fallback

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

        if config:
            self.click_timeout_ms = ClickTimeoutMs(config.click_timeout_ms)
            self.try_enter_key_fallback = TryEnterKeyFallbackFlag(config.try_enter_key_fallback)

        # Strategy 1: Iterate verified DOM send selectors
        for sel in SEND_SELECTORS:
            try:
                locator = page.locator(sel)
                if locator.count() > 0 and locator.is_visible() and locator.is_enabled():
                    locator.click(timeout=self.click_timeout_ms)
                    log.info("Send button clicked via: %s", sel)
                    emitter.emit(EVENT_SEND_CLICKED, {"selector": sel})
                    return
            except Error as e:
                log.warning("Selector '%s' failed: %s", sel, e)
                continue
            except Exception as e:
                log.error("Unexpected error with selector '%s': %s", sel, e)
                continue

        # Strategy 2: Enter key fallback on input element
        if self.try_enter_key_fallback:
            try:
                textarea = page.locator(TEXTAREA_SELECTOR)
                if textarea.count() > 0:
                    textarea.press("Enter")
                    log.info("Enter key pressed (send button not found)")
                    emitter.emit(EVENT_SEND_CLICKED, {"selector": "Enter"})
                    return
            except Error as e:
                log.warning("Enter fallback failed: %s", e)

        raise SendDispatchError("Failed to send: no valid send button and Enter fallback failed")

    def count_messages(self, page: Page) -> MessageCount:
        """Count chat turns using JS evaluate."""
        try:
            count = page.evaluate(_JS_COUNT_TURNS)
            if isinstance(count, int) and count > 0:
                return MessageCount(count)
        except Error:
            pass
        # fallback: CSS selector
        try:
            return MessageCount(page.locator(COMBINED_MESSAGE_SELECTOR).count())
        except Error:
            return MessageCount(0)

    def latest_message_text(self, page: Page) -> ResponseText | None:
        """Get the longest text block on page excluding input/UI chrome."""
        try:
            text = page.evaluate(_JS_GET_RESPONSE_TEXT)
            if text and len(text.strip()) > 0:
                return ResponseText(str(text.strip()))
        except Error:
            pass
        # fallback: CSS selector
        try:
            locator = page.locator(COMBINED_MESSAGE_SELECTOR)
            if locator.count() > 0:
                text = locator.last.text_content()
                if text is not None:
                    return ResponseText(str(text.strip()))
        except Error:
            pass
        return None


# Module-level convenience functions
def click_send(page: Page, emitter: LifecycleEmitter, config: SenderConfig | None = None, document_parsed: bool = True) -> None:
    """Click send button (module-level convenience)."""
    dispatcher = SendDispatcher()
    dispatcher.click_send(page, emitter, config, document_parsed)


def count_messages(page: Page) -> int:
    """Count messages (module-level convenience)."""
    dispatcher = SendDispatcher()
    return dispatcher.count_messages(page)


def latest_message_text(page: Page) -> str | None:
    """Get latest message text (module-level convenience)."""
    dispatcher = SendDispatcher()
    return dispatcher.latest_message_text(page)
