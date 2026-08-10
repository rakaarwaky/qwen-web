"""Send button click and message counting."""
from __future__ import annotations

from playwright.sync_api import Page, Error as PlaywrightError

from .types import (
    LifecycleEmitter,
    MESSAGE_SELECTORS,
    SEND_SELECTORS,
    EVENT_SEND_CLICKED,
)
from .observability import get_logger

log = get_logger("sender")

TEXTAREA_SELECTOR = "textarea.message-input-textarea"


def click_send(page: Page, emitter: LifecycleEmitter) -> None:
    """Click send button — tries all verified selectors, falls back to Enter key."""
    for sel in SEND_SELECTORS:
        try:
            locator = page.locator(sel)
            if locator.count() > 0 and locator.is_visible() and locator.is_enabled():
                locator.click(timeout=3_000)
                log.info("Send button clicked via: %s", sel)
                emitter.emit(EVENT_SEND_CLICKED, {"selector": sel})
                return
        except PlaywrightError as e:
            log.warning("Selector '%s' failed: %s", sel, e)
            continue
        except Exception as e:
            log.error("Unexpected error with selector '%s': %s", sel, e)
            continue

    try:
        textarea = page.locator(TEXTAREA_SELECTOR)
        if textarea.count() > 0:
            textarea.press("Enter")
            log.info("Enter key pressed (send button not found)")
            emitter.emit(EVENT_SEND_CLICKED, {"selector": "Enter"})
            return
    except PlaywrightError as e:
        log.warning("Enter fallback failed: %s", e)

    raise RuntimeError("Failed to send: no valid send button and Enter fallback failed")


def count_messages(page: Page) -> int:
    """Count assistant messages using verified selectors from config."""
    for sel in MESSAGE_SELECTORS:
        count = page.locator(sel).count()
        if count > 0:
            return count
    return 0


def latest_message_text(page: Page) -> str | None:
    """Get text of last assistant message using verified selectors from config."""
    for sel in MESSAGE_SELECTORS:
        locator = page.locator(sel)
        if locator.count() > 0:
            text = locator.last.text_content()
            if text is not None:
                return text.strip()
    return None
