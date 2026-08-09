#!/usr/bin/env python3
"""Deep headed DOM inspector: dump input-bar controls + exercise #filesUpload."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from config import CHAT_URL, DEFAULT_SESSION  # noqa: E402

OUT = Path(__file__).resolve().parent / "artifacts" / "dom_inspect2.json"


def main() -> int:
    from playwright.sync_api import sync_playwright

    probe = Path("/tmp/qwen_manual_probe.md")
    probe.write_text("# probe\nconfirm you read this file.\n", encoding="utf-8")

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

            # 1) Everything in the bottom 260px of the viewport
            bottom = page.evaluate("""() => {
                const H = window.innerHeight;
                const out = [];
                for (const el of document.querySelectorAll('*')) {
                    const r = el.getBoundingClientRect();
                    if (r.bottom < H - 260 || r.top > H) continue;
                    if (r.width === 0 || r.height === 0) continue;
                    const tag = el.tagName.toLowerCase();
                    if (!['button','div','span','input','textarea','svg','a'].includes(tag)) continue;
                    out.push({
                        tag,
                        role: el.getAttribute('role'),
                        aria_label: el.getAttribute('aria-label'),
                        title: el.getAttribute('title'),
                        cls: (el.className && el.className.toString().slice(0,140)),
                        text: (el.innerText||'').trim().slice(0,30),
                        clickable: (el.onclick!==null) || (getComputedStyle(el).cursor==='pointer'),
                    });
                }
                return out.slice(-40);
            }""")

            # 2) Exercise #filesUpload.upload then capture attachment card
            before = page.evaluate("""() => Array.from(document.querySelectorAll('*'))
                .filter(e=>/file|attach|card|chip|upload/i.test(e.className&&e.className.toString()))
                .map(e=>({cls:(e.className||'').toString().slice(0,120), txt:(e.innerText||'').trim().slice(0,40)}))""")
            try:
                page.locator("#filesUpload").first.set_input_files(str(probe), timeout=5000)
                page.wait_for_timeout(2000)
                upload_ok = True
                err = ""
            except Exception as e:
                upload_ok = False
                err = str(e)
            after = page.evaluate("""() => Array.from(document.querySelectorAll('*'))
                .filter(e=>/file|attach|card|chip|upload/i.test(e.className&&e.className.toString()))
                .map(e=>({cls:(e.className||'').toString().slice(0,120), txt:(e.innerText||'').trim().slice(0,40)}))""")

            info = {"bottom_controls": bottom, "upload_ok": upload_ok, "upload_error": err,
                    "attachment_classes_before": before, "attachment_classes_after": after}
            OUT.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(info, indent=2, ensure_ascii=False))
            input("\nDeep inspect done. ENTER to close: ")
            return 0
        finally:
            try:
                ctx.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
