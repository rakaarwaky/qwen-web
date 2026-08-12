"""Capabilities: prompt injection via DOM (AES403).

Implements IInjectionProtocol.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from modules.shared.src.contract_core_protocol import IInjectionProtocol
from modules.shared.src.taxonomy_core_constant import INPUT_SELECTORS
from modules.shared.src.taxonomy_core_vo import WaitTimeoutMs
from modules.shared.src.taxonomy_domain_error import ElementNotFoundError, PromptInjectionError

log = __import__("logging").getLogger("capabilities_prompt_injector")

DEFAULT_WAIT_TIMEOUT_MS = WaitTimeoutMs(10_000)


class PromptInjector(IInjectionProtocol):
    """Multi-strategy DOM text injection with verification."""

    def __init__(
        self,
        wait_timeout_ms: WaitTimeoutMs = DEFAULT_WAIT_TIMEOUT_MS,
        typing_delay_ms: int = 10,
        verify_injection: bool = True,
    ) -> None:
        self.wait_timeout_ms = wait_timeout_ms
        self.typing_delay_ms = typing_delay_ms
        self.verify_injection = verify_injection

    def find_input(self, page: Page, config: dict[str, Any] | None = None) -> Any:
        """Find input element using selector fallbacks."""
        cfg = config or {}
        start_timeout = max(1000, cfg.get("wait_timeout_ms", self.wait_timeout_ms) // len(INPUT_SELECTORS))

        for selector in INPUT_SELECTORS:
            try:
                el = page.wait_for_selector(selector, state="visible", timeout=start_timeout)
                if el:
                    log.debug("Found input element matching selector: %s", selector)
                    return el
            except (PlaywrightTimeoutError, PlaywrightError):
                continue

        # Final attempt with full timeout on primary selector
        primary = INPUT_SELECTORS[0]
        try:
            el = page.wait_for_selector(primary, timeout=cfg.get("wait_timeout_ms", self.wait_timeout_ms))
            if el:
                return el
        except (PlaywrightTimeoutError, PlaywrightError) as e:
            raise ElementNotFoundError(
                f"Timed out waiting for input selector '{primary}' on chat.qwen.ai: {e}"
            ) from e

        raise ElementNotFoundError(
            "Could not locate input element on chat.qwen.ai. UI may have changed."
        )

    def inject_text(self, page: Page, text: str, config: dict[str, Any] | None = None) -> None:
        """Inject text into input via multi-tier strategy with automatic validation."""
        if not text or not text.strip():
            raise PromptInjectionError("Cannot inject empty or whitespace-only prompt text.")

        cfg = config or {}
        el = self.find_input(page, cfg)

        try:
            el.focus()
        except PlaywrightError as e:
            log.warning("Element focus failed before injection: %s", e)

        # Strategy 1: React value setter for textarea
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
            if success and (not cfg.get("verify_injection", self.verify_injection) or self._verify_injection(el)):
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
            if success and (not cfg.get("verify_injection", self.verify_injection) or self._verify_injection(el)):
                log.info("Prompt injected via ContentEditable setter (%d chars)", len(text))
                return
        except PlaywrightError as e:
            log.debug("ContentEditable injection strategy failed: %s", e)

        # Strategy 3: Playwright fill()
        try:
            log.debug("Falling back to Playwright fill()")
            el.fill(text)
            if not cfg.get("verify_injection", self.verify_injection) or self._verify_injection(el):
                log.info("Prompt injected via Playwright fill() (%d chars)", len(text))
                return
        except PlaywrightError as e:
            log.warning("fill() failed: %s — falling back to type()", e)

        # Strategy 4: Playwright type()
        try:
            log.debug("Falling back to Playwright type()")
            el.type(text, delay=cfg.get("typing_delay_ms", self.typing_delay_ms))
            if not cfg.get("verify_injection", self.verify_injection) or self._verify_injection(el):
                log.info("Prompt injected via Playwright type() (%d chars)", len(text))
                return
        except PlaywrightError as exc:
            raise PromptInjectionError(f"All injection strategies failed for prompt: {exc}") from exc

        raise PromptInjectionError("All injection strategies executed but input verification failed.")

    def _verify_injection(self, el: Any) -> bool:
        """Verify that text is non-empty inside the input element."""
        try:
            val = el.evaluate(
                "(el) => el.value !== undefined ? el.value : (el.innerText || el.textContent || '')"
            )
            return bool(val and len(str(val).strip()) > 0)
        except Exception:
            return False


def find_input(page: Page, config: dict[str, Any] | None = None) -> Any:
    """Find input element (module-level convenience function)."""
    injector = PromptInjector()
    return injector.find_input(page, config)


def inject_text(page: Page, text: str, config: dict[str, Any] | None = None) -> None:
    """Inject text (module-level convenience function)."""
    injector = PromptInjector()
    injector.inject_text(page, text, config)


def type_slowly(_page: Page, textarea: Any, text: str, delay_ms: int = 30) -> None:
    """Type text character-by-character using Playwright's native type()."""
    if not text:
        return
    try:
        textarea.type(text, delay=delay_ms)
    except PlaywrightError as e:
        raise PromptInjectionError(f"Native typing failed: {e}") from e


def _verify_injection(el: Any) -> bool:
    """Verify that text is non-empty inside the input element (module-level convenience)."""
    return PromptInjector()._verify_injection(el)
