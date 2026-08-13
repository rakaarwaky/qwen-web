"""DOM query utilities for Playwright pages.

Utility layer (utility_core_dom_query): stateless functions for DOM reading.
Consumed by SendDispatcher, StreamMonitor, and Agent.
Taxonomy constants + Playwright Page only.
"""

from __future__ import annotations

from playwright.sync_api import Error, Page

from modules.shared.src.taxonomy_core_constant import (
    COMBINED_MESSAGE_SELECTOR,
    JS_COUNT_TURNS,
    JS_GET_RESPONSE_TEXT,
    SEND_SELECTORS,
)
from modules.shared.src.taxonomy_core_vo import MessageCount, ResponseText


def count_messages(page: Page) -> MessageCount:
    """Count chat turns via injected JS with locator fallback.

    Tier 1: injected JS (JS_COUNT_TURNS) when it yields a positive int.
    Tier 2: combined message-selector locator count.
    Fallback: MessageCount(0).

    Returns
    -------
    MessageCount
        Number of message elements matching turn selectors.

    """
    try:
        count = page.evaluate(JS_COUNT_TURNS)
        if isinstance(count, int) and count > 0:
            return MessageCount(count)
    except Error:
        pass
    try:
        return MessageCount(page.locator(COMBINED_MESSAGE_SELECTOR).count())
    except Error:
        return MessageCount(0)


def latest_message_text(page: Page) -> ResponseText | None:
    """Extract the latest assistant response text via injected JS with locator fallback.

    Tier 1: injected JS (JS_GET_RESPONSE_TEXT) when it yields non-empty text.
    Tier 2: combined message-selector locator's last text content.
    Fallback: None.

    Returns
    -------
    ResponseText | None
        Trimmed text, or None when nothing is available.

    """
    try:
        text = page.evaluate(JS_GET_RESPONSE_TEXT)
        if text and isinstance(text, str) and len(text.strip()) > 0:
            return ResponseText(str(text.strip()))
    except Error:
        pass
    try:
        locator = page.locator(COMBINED_MESSAGE_SELECTOR)
        if locator.count() > 0:
            text = locator.last.text_content()
            if text is not None:
                return ResponseText(str(text.strip()))
    except Error:
        pass
    return None


def click_send(page: Page, config: object = None) -> None:
    """Click the send button via multiple selector strategies.

    Falls back to Enter key when no visible send button is found.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    config : optional
        SenderConfig or None — uses the module default if omitted.

    """
    clicked = False
    for selector in SEND_SELECTORS:
        try:
            loc = page.locator(selector).first
            if loc.is_visible(timeout=3000):
                loc.click()
                clicked = True
                break
        except Exception:
            continue
    if not clicked:
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass
