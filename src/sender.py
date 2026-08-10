"""Enterprise-grade send dispatcher module for Qwen Web UI.

Provides multi-strategy send button triggers, keyboard fallbacks, and message element counting.
"""

from __future__ import annotations

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from .observability import get_logger
from .types import (
    DEFAULT_SENDER_CONFIG,
    EVENT_SEND_CLICKED,
    MESSAGE_SELECTORS,
    SEND_SELECTORS,
    LifecycleEmitter,
    SendDispatchError,
    SenderConfig,
)

log = get_logger("sender")

TEXTAREA_SELECTOR = "textarea.message-input-textarea"
COMBINED_MESSAGE_SELECTOR = ", ".join(MESSAGE_SELECTORS)

# JS that finds the AI response text in the live Qwen DOM.
# Strategy 1: look for known chat log containers (#chatLog, virtual-list, etc.)
# Strategy 2: find the longest text block that is NOT inside known Qwen UI chrome elements.
# Exclusion list is derived from live DOM inspection of chat.qwen.ai.
_JS_GET_RESPONSE_TEXT = """
() => {
    // Strategy 1: known chat log containers - try last child text
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

    // Strategy 2: longest text outside known Qwen UI chrome
    // These class substrings identify UI chrome to skip:
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
}
"""

_JS_COUNT_TURNS = """
() => {
    var turns = document.querySelectorAll(
        '[class*="chat-message"], [class*="message-item"], [class*="virtual-list-item"], [class*="turn"]'
    );
    return turns.length;
}
"""


def click_send(
    page: Page,
    emitter: LifecycleEmitter,
    config: SenderConfig | None = None,
    document_parsed: bool = True,
) -> None:
    """Click the prompt send button using verified selectors with keyboard Enter fallback.

    Args:
        page: Playwright Page instance.
        emitter: LifecycleEmitter for event notification.
        config: Optional SenderConfig instance.
        document_parsed: Bool indicating if document parsed event has been released.

    Raises:
        SendDispatchError: If document_parsed is False or no valid send trigger succeeds.

    """
    if not document_parsed:
        raise SendDispatchError("Cannot send prompt: document attachment parsing (EVENT_DOCUMENT_PARSED) is incomplete")

    cfg = config or DEFAULT_SENDER_CONFIG

    # Strategy 1: Iterate verified DOM send selectors
    for sel in SEND_SELECTORS:
        try:
            locator = page.locator(sel)
            if locator.count() > 0 and locator.is_visible() and locator.is_enabled():
                locator.click(timeout=cfg.click_timeout_ms)
                log.info("Send button clicked via: %s", sel)
                emitter.emit(EVENT_SEND_CLICKED, {"selector": sel})
                return
        except PlaywrightError as e:
            log.warning("Selector '%s' failed: %s", sel, e)
            continue
        except Exception as e:
            log.error("Unexpected error with selector '%s': %s", sel, e)
            continue

    # Strategy 2: Enter key fallback on input element
    if cfg.try_enter_key_fallback:
        try:
            textarea = page.locator(TEXTAREA_SELECTOR)
            if textarea.count() > 0:
                textarea.press("Enter")
                log.info("Enter key pressed (send button not found)")
                emitter.emit(EVENT_SEND_CLICKED, {"selector": "Enter"})
                return
        except PlaywrightError as e:
            log.warning("Enter fallback failed: %s", e)

    raise SendDispatchError("Failed to send: no valid send button and Enter fallback failed")


def count_messages(page: Page) -> int:
    """Count chat turns using JS evaluate — robust against CSS modules and virtual DOM.

    Args:
        page: Playwright Page instance.

    Returns:
        Number of detected chat turn elements.

    """
    try:
        count = page.evaluate(_JS_COUNT_TURNS)
        if isinstance(count, int) and count > 0:
            return count
    except PlaywrightError:
        pass
    # fallback: CSS selector
    try:
        return page.locator(COMBINED_MESSAGE_SELECTOR).count()
    except PlaywrightError:
        return 0


def latest_message_text(page: Page) -> str | None:
    """Get the longest text block on the page excluding input/UI chrome — JS-based.

    Uses JS evaluate to find the largest text node outside input/header/footer areas,
    which is robust against Qwen's CSS module class names and virtual list rendering.

    Args:
        page: Playwright Page instance.

    Returns:
        Cleaned text string of the latest AI response, or None if not found.

    """
    try:
        text = page.evaluate(_JS_GET_RESPONSE_TEXT)
        if text and len(text.strip()) > 0:
            return text.strip()
    except PlaywrightError:
        pass
    # fallback: CSS selector
    try:
        locator = page.locator(COMBINED_MESSAGE_SELECTOR)
        if locator.count() > 0:
            text = locator.last.text_content()
            if text is not None:
                return text.strip()
    except PlaywrightError:
        pass
    return None
