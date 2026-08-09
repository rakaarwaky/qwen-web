#!/usr/bin/env python3
"""Headed DOM inspector for the Qwen chat input bar.

Dumps the real current DOM structure around the input / send / attachment
controls so we can update src/config.py selectors accurately. Non-destructive.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import CHAT_URL, DEFAULT_SESSION  # noqa: E402

OUT = Path(__file__).resolve().parent / "artifacts" / "dom_inspect.json"


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(DEFAULT_SESSION),
            headless=False,
            permissions=["clipboard-read", "clipboard-write"],
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            viewport={"width": 1280, "height": 800},
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(2500)

            info: dict = {}

            # Does #filesUpload still exist?
            info["has_filesUpload"] = bool(page.query_selector("#filesUpload"))

            # Inspect the input bar region: roles, aria-labels, placeholders
            info["inputs"] = page.evaluate("""() => {
                const out = [];
                for (const el of document.querySelectorAll('textarea, input, [contenteditable=\"true\"], [role=\"textbox\"]')) {
                    out.push({
                        tag: el.tagName,
                        role: el.getAttribute('role'),
                        aria_label: el.getAttribute('aria-label'),
                        placeholder: el.getAttribute('placeholder'),
                        contenteditable: el.getAttribute('contenteditable'),
                        class: el.className && el.className.toString().slice(0, 120),
                    });
                }
                return out;
            }""")

            # Buttons near the input (aria-label / title / svg use href)
            info["buttons"] = page.evaluate("""() => {
                const out = [];
                for (const b of document.querySelectorAll('button, [role=\"button\"]')) {
                    const rect = b.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) continue;
                    if (rect.top < window.innerHeight - 250) continue; // only bottom input area
                    const label = b.getAttribute('aria-label') || b.getAttribute('title') || b.innerText.trim().slice(0, 40);
                    const use = b.querySelector('use');
                    const svg = b.querySelector('svg');
                    out.push({
                        label: label,
                        aria_label: b.getAttribute('aria-label'),
                        class: (b.className && b.className.toString().slice(0, 120)),
                        disabled: b.disabled,
                        svg_use_href: use && use.getAttribute('href'),
                        svg_class: svg && (svg.getAttribute('class') || '').slice(0, 80),
                    });
                }
                return out;
            }""")

            # Plus button: does clicking it open a file chooser?
            plus = None
            for b in info["buttons"]:
                if b["aria_label"] and ("add" in b["aria_label"].lower() or "attach" in b["aria_label"].lower() or "upload" in b["aria_label"].lower()):
                    plus = b
                    break
            info["plus_button"] = plus

            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(info, indent=2, ensure_ascii=False))
            input("\nInspect done. Press ENTER to close: ")
            return 0
        finally:
            try:
                ctx.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
