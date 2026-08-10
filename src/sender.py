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


def click_send(
    page: Page,
    emitter: LifecycleEmitter,
    config: SenderConfig | None = None,
) -> None:
    """Click the prompt send button using verified selectors with keyboard Enter fallback.

    Args:
        page: Playwright Page instance.
        emitter: LifecycleEmitter for event notification.
        config: Optional SenderConfig instance.

    Raises:
        SendDispatchError: If no valid send trigger succeeds.
    """
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
    """Count assistant messages using combined verified selectors.

    Args:
        page: Playwright Page instance.

    Returns:
        Number of matching message elements found.
    """
    try:
        return page.locator(COMBINED_MESSAGE_SELECTOR).count()
    except PlaywrightError:
        for sel in MESSAGE_SELECTORS:
            count = page.locator(sel).count()
            if count > 0:
                return count
        return 0


def latest_message_text(page: Page) -> str | None:
    """Get text content of the last assistant message.

    Args:
        page: Playwright Page instance.

    Returns:
        Cleaned text string of the latest message, or None if no messages found.
    """
    try:
        locator = page.locator(COMBINED_MESSAGE_SELECTOR)
        if locator.count() > 0:
            text = locator.last.text_content()
            if text is not None:
                return text.strip()
    except PlaywrightError:
        pass

    for sel in MESSAGE_SELECTORS:
        locator = page.locator(sel)
        if locator.count() > 0:
            text = locator.last.text_content()
            if text is not None:
                return text.strip()
    return None
