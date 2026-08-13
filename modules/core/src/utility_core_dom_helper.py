"""DOM helper utilities for Playwright pages.

Utility layer (utility_core_dom_helper): stateless functions for DOM interaction —
visibility checks, click helpers, locator selection, and selector-fallback iteration.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

from playwright.sync_api import Locator, Page

T = TypeVar("T")


def try_selectors(
    page: Page,
    selectors: Sequence[str],
    action: Callable[[Locator], T | None],
    timeout_ms: int = 1000,
) -> list[T]:
    """Iterate selectors, applying *action* to each visible locator.

    Swallows exceptions per-selector so iteration continues on failure.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    selectors : Sequence[str]
        CSS or XPath selectors to try in order.
    action : Callable[[Locator], T | None]
        Function applied to the first matching locator for each selector.
    timeout_ms : int
        Visibility timeout in milliseconds.

    Returns
    -------
    list[T]
        Results from successful action calls (empty when none matched).
    """
    results: list[T] = []
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.is_visible(timeout=timeout_ms):
                results.append(action(loc))
        except Exception:
            continue
    return results


def first_visible_locator(
    page: Page,
    selectors: Sequence[str],
    timeout_ms: int = 1000,
) -> Locator | None:
    """Return the first visible Locator matching any of the given selectors.

    Uses try_selectors internally to avoid duplicated selector-loop logic.

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
    results = try_selectors(page, selectors, lambda loc: loc, timeout_ms)
    return results[0] if results else None


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
    results = try_selectors(page, selectors, lambda loc: (loc.click(), True)[1], timeout_ms)
    return len(results) > 0 and results[0] is True


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
