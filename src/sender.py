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

# JS that finds the last AI response block by looking for the largest text
# element that is not inside the input/header/footer areas.
_JS_GET_RESPONSE_TEXT = """
() => {
    var skip = ['SCRIPT','STYLE','TEXTAREA','INPUT','BUTTON','HEADER','FOOTER','NAV'];
    var inputBox = document.querySelector('textarea.message-input-textarea');
    var best = null;
    var bestLen = 0;
    var all = document.querySelectorAll('div, p, pre, section, article');
    for (var i = 0; i < all.length; i++) {
        var el = all[i];
        if (skip.indexOf(el.tagName) >= 0) continue;
        if (inputBox && inputBox.contains(el)) continue;
        var pEl = el.parentElement;
        var skip2 = false;
        while (pEl) {
            if (pEl.className && typeof pEl.className === 'string' &&
                (pEl.className.indexOf('message-input') >= 0 ||
                 pEl.className.indexOf('header') >= 0 ||
                 pEl.className.indexOf('footer') >= 0 ||
                 pEl.className.indexOf('feedback') >= 0 ||
                 pEl.className.indexOf('downLoad') >= 0)) {
                skip2 = true; break;
            }
            pEl = pEl.parentElement;
        }
        if (skip2) continue;
        var txt = (el.innerText || '').trim();
        if (txt.length > bestLen) {
            bestLen = txt.length;
            best = txt;
        }
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
