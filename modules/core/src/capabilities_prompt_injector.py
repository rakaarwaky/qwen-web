"""Capabilities: prompt injection via DOM (AES403).

Implements IInjectionProtocol.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Error, Page

from modules.core.src.utility_core_dom_helper import first_visible_element_handle
from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src.contract_core_protocol import IInjectionProtocol
from modules.shared.src.taxonomy_config_vo import DEFAULT_INJECTOR_CONFIG, InjectorConfig
from modules.shared.src.taxonomy_core_error import ElementNotFoundError, PromptInjectionError

log = get_logger("capabilities_prompt_injector")


# Block 1: Class Definition & Constructor


class PromptInjector(IInjectionProtocol):
    """Multi-strategy DOM text injection with verification."""

    def __init__(self, config: InjectorConfig = DEFAULT_INJECTOR_CONFIG) -> None:
        """Initialize with an InjectorConfig VO."""
        self.config = config

    # ─── Block 2: Public Contract (IInjectionProtocol ONLY) ──
    def find_input(self, page: Page, config: InjectorConfig | None = None) -> Any:
        """Find input element using selector fallbacks."""
        cfg = config or self.config
        selectors = tuple(cfg.input_selectors)
        start_timeout = max(1000, int(cfg.wait_timeout_ms) // len(selectors))

        el = first_visible_element_handle(page, selectors, start_timeout)
        if el:
            return el

        # Final attempt with full timeout on primary selector
        primary = selectors[0]
        try:
            el = page.wait_for_selector(primary, timeout=int(cfg.wait_timeout_ms))
            if el:
                return el
        except (TimeoutError, Error) as e:
            raise ElementNotFoundError(f"Timed out waiting for input selector '{primary}' on chat.qwen.ai: {e}") from e
        raise ElementNotFoundError("Could not locate input element on chat.qwen.ai. UI may have changed.")

    def inject_text(self, page: Page, text: str, config: InjectorConfig | None = None) -> None:
        """Inject text into input via multi-tier strategy with automatic validation."""
        if not text or not text.strip():
            raise PromptInjectionError("Cannot inject empty or whitespace-only prompt text.")

        cfg = config or self.config
        el = self.find_input(page, cfg)

        try:
            el.focus()
        except Error as e:
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
            if success and (not cfg.verify_injection or self._verify_injection(el)):
                log.info("Prompt injected via React value-setter (%d chars)", len(text))
                return
        except Error as e:
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
            if success and (not cfg.verify_injection or self._verify_injection(el)):
                log.info("Prompt injected via ContentEditable setter (%d chars)", len(text))
                return
        except Error as e:
            log.debug("ContentEditable injection strategy failed: %s", e)

        # Strategy 3: Playwright fill()
        try:
            log.debug("Falling back to Playwright fill()")
            el.fill(text)
            if not cfg.verify_injection or self._verify_injection(el):
                log.info("Prompt injected via Playwright fill() (%d chars)", len(text))
                return
        except Error as e:
            log.warning("fill() failed: %s — falling back to type()", e)

        # Strategy 4: Playwright type()
        try:
            log.debug("Falling back to Playwright type()")
            el.type(text, delay=cfg.typing_delay_ms)
            if not cfg.verify_injection or self._verify_injection(el):
                log.info("Prompt injected via Playwright type() (%d chars)", len(text))
                return
        except Error as exc:
            raise PromptInjectionError(f"All strategies failed for prompt: {exc}") from exc

        raise PromptInjectionError("All strategies executed but input verification failed.")

    # Block 3: Dunder Methods, Factories & Helpers

    def _verify_injection(self, el: Any) -> bool:
        """Verify that text is non-empty inside the input element."""
        try:
            val = el.evaluate("(el) => el.value !== undefined ? el.value : (el.innerText || el.textContent || '')")
            return bool(val and len(str(val).strip()) > 0)
        except Exception:
            return False

    def __repr__(self) -> str:
        """Return string representation of PromptInjector."""
        return f"PromptInjector(config={self.config!r})"
