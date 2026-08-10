"""Prompt injection into Qwen's textarea."""
from __future__ import annotations

from playwright.sync_api import Page, ElementHandle, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

from .types import AuthRequiredError, ElementNotFoundError, PromptInjectionError
from .observability import get_logger

log = get_logger("prompt_injector")

PRIMARY_TEXTAREA = "textarea.message-input-textarea"
FALLBACK_TEXTAREA = "textarea"


def find_input(page: Page) -> ElementHandle:
    """Find textarea.input — proven selector from live test."""
    try:
        el = page.wait_for_selector(PRIMARY_TEXTAREA, timeout=10_000)
        if not el:
            raise ElementNotFoundError(
                "Could not find textarea on chat.qwen.ai. "
                "UI may have changed — check selector or run 'qwc --login' to re-authenticate."
            )
        return el
    except PlaywrightTimeoutError as e:
        raise ElementNotFoundError(f"Timed out waiting for textarea on chat.qwen.ai: {e}") from e
    except PlaywrightError as e:
        raise ElementNotFoundError(f"Browser error finding textarea: {e}") from e


def inject_text(page: Page, text: str) -> None:
    """Inject text via React value-setter with fallback to fill() and type()."""
    el = page.query_selector(PRIMARY_TEXTAREA) or page.query_selector(FALLBACK_TEXTAREA)
    if not el:
        raise ElementNotFoundError("Textarea not found for injection.")
    try:
        el.focus()
    except PlaywrightError as e:
        log.warning("Focus failed: %s", e)

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
            try:
                el.type(text, delay=10)
            except PlaywrightError as exc:
                raise PromptInjectionError(f"All injection strategies failed for prompt: {exc}") from exc

    log.info("Prompt injected (%d chars)", len(text))


def type_slowly(page: Page, textarea: ElementHandle, text: str, delay_ms: int = 30) -> None:
    """Type text character-by-character using Playwright's native type()."""
    try:
        textarea.type(text, delay=delay_ms)
    except PlaywrightError as e:
        raise PromptInjectionError(f"Native typing failed: {e}") from e
