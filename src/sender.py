"""Enterprise-grade send dispatcher module for Qwen Web UI.

Provides multi-strategy send button triggers, keyboard fallbacks, and message element counting.
"""

from __future__ import annotations

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from .observability import get_logger
from .types import (
    DEFAULT_SENDER_CONFIG,
    EVENT_DOCUMENT_PARSED,
    EVENT_PROMPT_INJECTED,
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
    // Target exact Qwen assistant response elements excluding thinking/thought blocks
    var selectors = [
        '.chat-message-assistant .markdown-body:not(.thinking):not([class*="thought"])',
        '.chat-message-assistant:not(.thinking)',
        '[class*="assistant"] .markdown-body:not(.thinking):not([class*="thought"])',
        '[class*="assistant"] [class*="markdown"]:not(.thinking):not([class*="thought"])',
        '[data-role="assistant"] .markdown-body:not(.thinking):not([class*="thought"])',
        '.qwen-markdown:not(.thinking):not([class*="thought"])'
    ];
    for (var i = 0; i < selectors.length; i++) {
        var els = document.querySelectorAll(selectors[i]);
        if (els.length > 0) {
            for (var j = els.length - 1; j >= 0; j--) {
                var el = els[j];
                if (el.closest && (el.closest('.thinking') || el.closest('[class*="thought"]'))) continue;
                var txt = (el.innerText || el.textContent || '').trim();
                if (txt.length > 0) return txt;
            }
        }
    }
    return null;
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
    prompt_injected: bool = True,
) -> None:
    """Click the Send button or trigger Enter fallback.

    Args:
        page: Playwright Page instance.
        emitter: LifecycleEmitter for event notification.
        config: Optional SenderConfig instance.
        document_parsed: Bool indicating if document parsed event has been released.
        prompt_injected: Bool indicating if prompt injected event (EVENT_PROMPT_INJECTED) has been released.

    Raises:
        SendDispatchError: If document_parsed or prompt_injected is False or no valid send trigger succeeds.

    """
    if not document_parsed:
        raise SendDispatchError(f"Cannot send prompt: document attachment parsing ({EVENT_DOCUMENT_PARSED}) is incomplete")
    if not prompt_injected:
        raise SendDispatchError(f"Cannot send prompt: prompt injection ({EVENT_PROMPT_INJECTED}) is incomplete")

    cfg = config or DEFAULT_SENDER_CONFIG

    # Event Safeguard: Ensure no active parsing/processing file indicators remain in the DOM
    try:
        page.locator("[class*='file'], [class*='attachment'], [class*='card']").filter(has_text="Parsing").wait_for(
            state="hidden", timeout=30000
        )
    except Exception as e:
        log.debug("Parsing indicator check finished/bypassed: %s", e)
    for sel in SEND_SELECTORS:
        try:
            locator = page.locator(sel)
            if locator.count() > 0 and locator.is_visible() and locator.is_enabled():
                locator.click(timeout=cfg.click_timeout_ms)
                log.info("Send button clicked via: %s", sel)
                emitter.emit(EVENT_SEND_CLICKED, {"selector": sel})
                # Trigger native Enter press to ensure React dispatch if input is non-empty
                try:
                    textarea_el = page.locator(TEXTAREA_SELECTOR)
                    if textarea_el.count() > 0 and textarea_el.first.is_visible():
                        textarea_el.first.press("Enter")
                except Exception:
                    pass
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
                textarea.first.press("Enter")
                log.info("Enter key pressed (send button fallback)")
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
            return str(text.strip())
    except PlaywrightError:
        pass
    # fallback: CSS selector
    try:
        locator = page.locator(COMBINED_MESSAGE_SELECTOR)
        if locator.count() > 0:
            text = locator.last.text_content()
            if text is not None:
                return str(text.strip())
    except PlaywrightError:
        pass
    return None
