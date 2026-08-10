"""Prompt injection into Qwen's textarea."""
from __future__ import annotations

import time
from typing import Any

from playwright.sync_api import Page

from .types import AuthRequiredError
from .observability import get_logger

log = get_logger("prompt_injector")


def find_input(page: Page):
    """Find textarea.input — proven selector from live test."""
    el = page.wait_for_selector('textarea.message-input-textarea', timeout=10_000)
    if not el:
        raise AuthRequiredError(
            "Could not find textarea on chat.qwen.ai. Please run 'qwc --login' to re-authenticate."
        )
    return el


def inject_text(page: Page, text: str) -> None:
    """Inject text via React value-setter (fill() doesn't trigger React state)."""
    el = page.query_selector('textarea.message-input-textarea') or page.query_selector('textarea')
    if not el:
        raise AuthRequiredError("Textarea not found for injection.")
    el.focus()
    try:
        page.evaluate("""(text) => {
            const el = document.querySelector('textarea.message-input-textarea') || document.querySelector('textarea');
            if (!el) throw new Error('textarea not found');
            const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            setter.call(el, text);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""", text)
    except Exception:
        page.evaluate("""(text) => {
            const el = document.querySelector('textarea.message-input-textarea') || document.querySelector('textarea');
            if (!el) throw new Error('textarea not found');
            navigator.clipboard.writeText(text);
            el.focus();
            el.setSelectionRange(0, 0);
            document.execCommand('paste');
        }""", text)
    log.info("Prompt injected via React value-setter (%d chars)", len(text))


def type_slowly(page: Page, textarea: Any, text: str, delay_ms: float = 30) -> None:
    """Type text character-by-character into a textarea with per-character delays."""
    for char in text:
        textarea.press(char)
        time.sleep(delay_ms / 1000)
