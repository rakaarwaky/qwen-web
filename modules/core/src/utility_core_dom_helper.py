"""DOM helper utilities for Playwright pages.

Utility layer (utility_core_dom_helper): stateless functions for DOM interaction —
visibility checks, click helpers, locator selection.
"""

from __future__ import annotations

from collections.abc import Sequence

from playwright.sync_api import Locator, Page


def first_visible_locator(
    page: Page,
    selectors: Sequence[str],
    timeout_ms: int = 1000,
) -> Locator | None:
    """Return the first visible Locator matching any of the given selectors.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    selectors : Sequence[str]
        CSS or XPath selectors to try in order.
    timeout_ms : int
        Visibility timeout in milliseconds.

    Returns
    -------
    Locator | None
        First visible locator, or None if none match.

    """
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.is_visible(timeout=timeout_ms):
                return loc
        except Exception:
            continue
    return None


def click_first_visible_enabled(
    page: Page,
    selectors: Sequence[str],
    timeout_ms: int = 3000,
) -> bool:
    """Click the first visible and enabled button matching any selector.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    selectors : Sequence[str]
        Button selectors to try in order.
    timeout_ms : int
        Visibility timeout in milliseconds.

    Returns
    -------
    bool
        True if a matching button was clicked, False otherwise.

    """
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.is_visible(timeout=timeout_ms):
                loc.click()
                return True
        except Exception:
            continue
    return False


def is_selector_visible(page: Page, selector: str, timeout_ms: int = 1000) -> bool:
    """Check whether a single CSS selector produces a visible element.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    selector : str
        CSS or XPath selector.
    timeout_ms : int
        Visibility timeout in milliseconds.

    Returns
    -------
    bool
        True if a matching element is visible within the timeout.

    """
    try:
        loc = page.locator(selector).first
        return loc.is_visible(timeout=timeout_ms)
    except Exception:
        return False
