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
from modules.core.src.utility_core_dom_action import click_first_visible_enabled


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

    Falls back to Enter key when no visible send button is found.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    config : optional
        SenderConfig or None — uses DEFAULT_SENDER_CONFIG if omitted.

    """
    if not click_first_visible_enabled(page, SEND_SELECTORS, timeout_ms=3000):
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass
