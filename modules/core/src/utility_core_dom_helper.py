"""DOM helper utilities for Playwright pages.

Utility layer (utility_core_dom_helper): stateless functions for DOM interaction —
visibility checks, click helpers, locator selection, and selector-fallback iteration.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import suppress
from typing import Any, TypeVar

from playwright.sync_api import Error, Locator, Page

from modules.shared.src.taxonomy_core_constant import SEND_SELECTORS

T = TypeVar("T")


def try_selectors(
    page: Page,
    selectors: Sequence[str],
    action: Callable[[Locator], T],
    timeout_ms: int = 1000,
    first_only: bool = False,
) -> list[T]:
    """Iterate selectors, applying *action* to each visible locator.

    Swallows exceptions per-selector so iteration continues on failure.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    selectors : Sequence[str]
        CSS or XPath selectors to try in order.
    action : Callable[[Locator], T]
        Function applied to the first matching locator for each selector.
    timeout_ms : int
        Visibility timeout in milliseconds.
    first_only : bool
        Stop iteration after the first successful action call.

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
                value = action(loc)
                if value is not None:
                    results.append(value)
                if first_only:
                    break
        except Error:
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
    results = try_selectors(page, selectors, lambda loc: loc, timeout_ms, first_only=True)
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
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if loc.is_visible(timeout=timeout_ms):
                loc.click()
                return True
        except Error:
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
    return any_visible_locator(page, selector, timeout_ms)


def any_visible_locator(
    page: Page,
    selectors: str | Sequence[str],
    timeout_ms: int = 1000,
) -> bool:
    """Return True if any of the given selectors matches a visible element.

    Only Playwright ``Error`` is swallowed per selector; unexpected
    exceptions propagate so callers can treat browser failures explicitly.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    selectors : str | Sequence[str]
        One selector or a sequence of CSS/XPath selectors to try in order.
    timeout_ms : int
        Visibility timeout in milliseconds.

    Returns
    -------
    bool
        True when at least one selector resolves to a visible element.

    """
    if isinstance(selectors, str):
        selectors = (selectors,)
    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() > 0 and loc.first.is_visible(timeout=timeout_ms):
                return True
        except Error:
            continue
    return False


def click_send(page: Page, _config: object = None) -> None:
    """Click send button via selector fallback, Enter key as last resort.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    config : optional
        Unused — kept for API compatibility.

    """
    clicked = click_first_visible_enabled(page, SEND_SELECTORS, timeout_ms=3000)
    if not clicked:
        with suppress(Exception):
            page.keyboard.press("Enter")


def is_any_visible(page: Page, selector: str) -> bool:
    """Check if any element matching selector is visible.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    selector : str
        CSS or XPath selector.

    Returns
    -------
    bool
        True when at least one matching element is visible.

    """
    return any_visible_locator(page, selector)


def first_visible_element_handle(
    page: Page,
    selectors: Sequence[str],
    timeout_ms: int = 1000,
) -> Any | None:
    """Return first visible ElementHandle via wait_for_selector, or None.

    Parameters
    ----------
    page : Page
        Active Playwright page.
    selectors : Sequence[str]
        CSS or XPath selectors to try in order.
    timeout_ms : int
        Visibility timeout per selector in milliseconds.

    Returns
    -------
    ElementHandle | None
        First visible handle, or None if none match.

    """
    for selector in selectors:
        try:
            el = page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
            if el:
                return el
        except Error:
            continue
    return None
