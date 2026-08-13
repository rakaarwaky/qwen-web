"""DOM query utilities for Playwright pages.

Utility layer (utility_core_dom_query): stateless functions for DOM reading.
Consumed by SendDispatcher, StreamMonitor, and Agent.
Taxonomy constants + Playwright Page only.
"""

from __future__ import annotations

from collections.abc import Sequence

from playwright.sync_api import Error, Page

from modules.shared.src.taxonomy_core_constant import (
    COMBINED_MESSAGE_SELECTOR,
    JS_COUNT_TURNS,
    JS_GET_RESPONSE_TEXT,
    SEND_SELECTORS,
)
from modules.shared.src.taxonomy_core_vo import MessageCount, ResponseText


def _try_selectors(page: Page, selectors: Sequence[str], action, timeout_ms: int = 1000):
    """Iterate selectors, applying *action* to each visible locator.

    Swallows exceptions per-selector so iteration continues on failure.
    """
    results = []
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            visible = loc.is_visible(timeout=timeout_ms)
        except Exception:
            visible = False
        if not visible:
            continue
        results.append(action(loc))
    return results


def _click_first_visible_enabled(page: Page, selectors: Sequence[str], timeout_ms: int = 3000) -> bool:
    """Click the first visible and enabled button matching any selector."""
    results = _try_selectors(page, selectors, lambda loc: (loc.click(), True)[1], timeout_ms)
    return len(results) > 0 and results[0] is True


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
    clicked = _click_first_visible_enabled(page, SEND_SELECTORS, timeout_ms=3000)
    if not clicked:
        try:
            page.keyboard.press("Enter")
        except Error:
            pass
