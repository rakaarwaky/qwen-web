"""Send button click and message counting."""
from __future__ import annotations

from playwright.sync_api import Page

from .types import (
    LifecycleEmitter,
    MESSAGE_SELECTORS,
    SEND_SELECTORS,
    EVENT_SEND_CLICKED,
)
from .observability import get_logger

log = get_logger("sender")


def click_send(page: Page, emitter: LifecycleEmitter) -> None:
    """Click send button — tries all verified selectors, falls back to Enter key."""
    for sel in SEND_SELECTORS:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible() and btn.is_enabled():
                btn.click(timeout=3_000)
                log.info("Send button clicked via: %s", sel)
                emitter.emit(EVENT_SEND_CLICKED, {"selector": sel})
                return
        except Exception:
            continue
    el = page.query_selector('textarea.message-input-textarea')
    if el:
        el.press("Enter")
        log.info("Enter key pressed (send button not found)")
        emitter.emit(EVENT_SEND_CLICKED, {"selector": "Enter"})


def count_messages(page: Page) -> int:
    """Count assistant messages using verified selectors from config."""
    for sel in MESSAGE_SELECTORS:
        count = page.evaluate("s => document.querySelectorAll(s).length", sel)
        if count and count > 0:
            return count
    return 0


def latest_message_text(page: Page) -> str | None:
    """Get text of last assistant message using verified selectors from config."""
    for sel in MESSAGE_SELECTORS:
        text = page.evaluate("s => { const msgs = document.querySelectorAll(s); return msgs.length > 0 ? msgs[msgs.length - 1].textContent.trim() : null; }", sel)
        if text:
            return text
    return None
