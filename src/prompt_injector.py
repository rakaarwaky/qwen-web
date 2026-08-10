"""Prompt injection into Qwen's textarea."""
from __future__ import annotations

from playwright.sync_api import Page, ElementHandle, Error as PlaywrightError

from .types import AuthRequiredError, ElementNotFoundError
from .observability import get_logger

log = get_logger("prompt_injector")

PRIMARY_TEXTAREA = "textarea.message-input-textarea"
FALLBACK_TEXTAREA = "textarea"


def find_input(page: Page) -> ElementHandle:
    """Find textarea.input — proven selector from live test."""
    el = page.wait_for_selector(PRIMARY_TEXTAREA, timeout=10_000)
    if not el:
        raise ElementNotFoundError(
            "Could not find textarea on chat.qwen.ai. "
            "UI may have changed — check selector or run 'qwc --login' to re-authenticate."
        )
    return el


def inject_text(page: Page, text: str) -> None:
    """Inject text via React value-setter (fill() doesn't trigger React state)."""
    el = page.query_selector(PRIMARY_TEXTAREA) or page.query_selector(FALLBACK_TEXTAREA)
    if not el:
        raise ElementNotFoundError("Textarea not found for injection.")
    el.focus()

    js_inject = """(text) => {
        const el = document.querySelector('textarea.message-input-textarea') || document.querySelector('textarea');
        if (!el) throw new Error('textarea not found');
        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        setter.call(el, text);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    }"""

    try:
        page.evaluate(js_inject, text)
    except PlaywrightError as e:
        log.warning("React value-setter failed: %s — falling back to fill()", e)
        try:
            el.fill(text)
        except PlaywrightError:
            log.warning("fill() failed — falling back to type()")
            el.type(text, delay=10)

    log.info("Prompt injected (%d chars)", len(text))


def type_slowly(page: Page, textarea: ElementHandle, text: str, delay_ms: int = 30) -> None:
    """Type text character-by-character using Playwright's native type()."""
    textarea.type(text, delay=delay_ms)
