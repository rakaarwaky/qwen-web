"""Enterprise-grade prompt injector module for Qwen Web UI.

Provides multi-strategy DOM text injection (React value setter, contenteditable innerText,
Playwright fill(), and native keystroke typing) with automated input verification and fallback support.
"""

from __future__ import annotations

from playwright.sync_api import (
    ElementHandle,
    Page,
)
from playwright.sync_api import (
    Error as PlaywrightError,
)
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from .observability import get_logger
from .types import (
    DEFAULT_INJECTOR_CONFIG,
    ElementNotFoundError,
    InjectorConfig,
    PromptInjectionError,
)

log = get_logger("prompt_injector")


def find_input(page: Page, config: InjectorConfig | None = None) -> ElementHandle:
    """Find input element using selector fallbacks.

    Args:
        page: Playwright Page instance.
        config: Optional InjectorConfig instance.

    Returns:
        ElementHandle pointing to the target input element.

    Raises:
        ElementNotFoundError: If no input element is found within timeout.

    """
    cfg = config or DEFAULT_INJECTOR_CONFIG
    start_timeout = max(1000, cfg.wait_timeout_ms // len(cfg.input_selectors))

    for selector in cfg.input_selectors:
        try:
            el = page.wait_for_selector(selector, state="visible", timeout=start_timeout)
            if el:
                log.debug("Found input element matching selector: %s", selector)
                return el
        except (PlaywrightTimeoutError, PlaywrightError):
            continue

    # Final attempt with full timeout on primary selector
    primary = cfg.input_selectors[0]
    try:
        el = page.wait_for_selector(primary, timeout=cfg.wait_timeout_ms)
        if el:
            return el
    except (PlaywrightTimeoutError, PlaywrightError) as e:
        raise ElementNotFoundError(
            f"Timed out waiting for input selector '{primary}' on chat.qwen.ai: {e}"
        ) from e

    raise ElementNotFoundError(
        "Could not locate input element on chat.qwen.ai. "
        "UI may have changed — check selector or re-authenticate."
    )


def _verify_injection(el: ElementHandle) -> bool:
    """Verify that text is non-empty inside the input element."""
    try:
        val = el.evaluate(
            "(el) => el.value !== undefined ? el.value : (el.innerText || el.textContent || '')"
        )
        return bool(val and len(str(val).strip()) > 0)
    except Exception:
        return False


def inject_text(page: Page, text: str, config: InjectorConfig | None = None) -> None:
    """Inject text into input via multi-tier strategy with automatic validation.

    Strategies attempted in sequence:
      1. React HTMLTextAreaElement prototype value setter + dispatchEvent
      2. ContentEditable / standard DOM innerText assignment
      3. Native Playwright fill()
      4. Keystroke typing (type())

    Args:
        page: Playwright Page instance.
        text: Prompt text string to inject.
        config: Optional InjectorConfig instance.

    Raises:
        PromptInjectionError: If text is invalid or all injection strategies fail.
        ElementNotFoundError: If input element cannot be located.

    """
    if not text or not text.strip():
        raise PromptInjectionError("Cannot inject empty or whitespace-only prompt text.")

    cfg = config or DEFAULT_INJECTOR_CONFIG
    el = find_input(page, config=cfg)

    try:
        el.focus()
    except PlaywrightError as e:
        log.warning("Element focus failed before injection: %s", e)

    # Strategy 1: React value setter for <textarea>
    js_react_inject = """(text) => {
        const selectors = ['textarea.message-input-textarea', 'textarea', '#chat-input', '.chat-input'];
        let target = null;
        for (const s of selectors) {
            const found = document.querySelector(s);
            if (found) { target = found; break; }
        }
        if (!target) return false;
        if (target.tagName.toLowerCase() === 'textarea') {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            setter.call(target, text);
            target.dispatchEvent(new Event('input', { bubbles: true }));
            target.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }
        return false;
    }"""

    try:
        success = page.evaluate(js_react_inject, text)
        if success and (not cfg.verify_injection or _verify_injection(el)):
            log.info("Prompt injected via React value-setter (%d chars)", len(text))
            return
    except PlaywrightError as e:
        log.debug("React value-setter strategy bypassed/failed: %s", e)

    # Strategy 2: ContentEditable innerText injection
    js_contenteditable_inject = """(text) => {
        const el = document.querySelector("div[contenteditable='true']");
        if (!el) return false;
        el.innerText = text;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        return true;
    }"""

    try:
        success = page.evaluate(js_contenteditable_inject, text)
        if success and (not cfg.verify_injection or _verify_injection(el)):
            log.info("Prompt injected via ContentEditable setter (%d chars)", len(text))
            return
    except PlaywrightError as e:
        log.debug("ContentEditable injection strategy failed: %s", e)

    # Strategy 3: Playwright fill()
    try:
        log.debug("Falling back to Playwright fill()")
        el.fill(text)
        if not cfg.verify_injection or _verify_injection(el):
            log.info("Prompt injected via Playwright fill() (%d chars)", len(text))
            return
    except PlaywrightError as e:
        log.warning("fill() failed: %s — falling back to type()", e)

    # Strategy 4: Playwright type()
    try:
        log.debug("Falling back to Playwright type()")
        el.type(text, delay=cfg.typing_delay_ms)
        if not cfg.verify_injection or _verify_injection(el):
            log.info("Prompt injected via Playwright type() (%d chars)", len(text))
            return
    except PlaywrightError as exc:
        raise PromptInjectionError(f"All injection strategies failed for prompt: {exc}") from exc

    raise PromptInjectionError("All injection strategies executed but input verification failed.")


def type_slowly(
    page: Page,
    textarea: ElementHandle,
    text: str,
    delay_ms: int = 30,
) -> None:
    """Type text character-by-character using Playwright's native type().

    Args:
        page: Playwright Page instance.
        textarea: Target ElementHandle.
        text: Text string to type.
        delay_ms: Delay in milliseconds between keypresses.

    Raises:
        PromptInjectionError: If typing fails.

    """
    if not text:
        return
    try:
        textarea.type(text, delay=delay_ms)
    except PlaywrightError as e:
        raise PromptInjectionError(f"Native typing failed: {e}") from e
