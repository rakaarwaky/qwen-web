"""DOM query utilities for Playwright pages.

Utility layer (utility_core_dom_query): stateless functions for DOM reading.
Consumed by SendDispatcher, StreamMonitor, and Agent.
Taxonomy constants + Playwright Page only.
"""

from __future__ import annotations

from playwright.sync_api import Page

from modules.shared.src.taxonomy_config_vo import DEFAULT_SENDER_CONFIG
from modules.shared.src.taxonomy_core_constant import (
    COMBINED_MESSAGE_SELECTOR,
    JS_COUNT_TURNS,
    JS_GET_RESPONSE_TEXT,
    SEND_SELECTORS,
)
from modules.shared.src.taxonomy_core_vo import MessageCount, ResponseText


def count_messages(page: Page) -> MessageCount:
    """Count chat turns via injected JS.

    Returns
    -------
    MessageCount
        Number of message elements matching turn selectors.

    """
    return MessageCount(page.evaluate(JS_COUNT_TURNS))


def latest_message_text(page: Page) -> ResponseText | None:
    """Extract the latest assistant response text via injected JS.

    Returns
    -------
    ResponseText | None
        Trimmed text if > 20 chars, else None.

    """
    text = page.evaluate(JS_GET_RESPONSE_TEXT)
    if text and isinstance(text, str):
        stripped = text.strip()
        if len(stripped) > 20:
            return ResponseText(stripped)
    return None


def click_send(page: Page, config: object = None) -> None:
    """Click the send button via multiple selector strategies.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    config : optional
        SenderConfig or None — uses DEFAULT_SENDER_CONFIG if omitted.

    """
    for selector in SEND_SELECTORS:
        try:
            loc = page.locator(selector).first
            if loc.is_visible(timeout=3000):
                loc.click()
                return
        except Exception:
            continue

    # Enter key fallback
    try:
        page.keyboard.press("Enter")
    except Exception:
        pass
