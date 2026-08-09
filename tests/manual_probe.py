#!/usr/bin/env python3
"""
Manual / smoke-check probe for qwen-web-automation (headed).

Validates the EXACT selectors and strategies the production code uses
(src/config.py + src/qwen_client.py) against the LIVE chat.qwen.ai DOM, and
writes a machine-readable snapshot of which selectors are still alive to
tests/artifacts/selectors_live.json. Re-run this after any Qwen UI change to
learn instantly which selectors broke.

Run (headed, visible window):
    python3 tests/manual_probe.py

Non-destructive: works on a throwaway file in /tmp, never the real input/ queue.
Screenshots land in tests/artifacts/.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import (  # noqa: E402
    CHAT_URL,
    DEFAULT_SESSION,
    NEW_CHAT_SELECTORS,
    INPUT_SELECTORS,
    SEND_SELECTORS,
    MESSAGE_SELECTORS,
)
from playwright.sync_api import sync_playwright  # noqa: E402

ART = Path(__file__).resolve().parent / "artifacts"
ART.mkdir(parents=True, exist_ok=True)


def _first_visible(page, selectors, timeout=1500):
    for sel in selectors:
        try:
            if page.locator(sel).first.is_visible(timeout=timeout):
                return sel
        except Exception:
            continue
    return None


def _make_probe_file() -> Path:
    p = Path("/tmp/qwen_manual_probe.md")
    p.write_text(
        "# Manual Probe\n\nThis is a throwaway test file. Please reply with a one-sentence "
        "confirmation that you can read this attached file.\n",
        encoding="utf-8",
    )
    return p


def main() -> int:
    probe = _make_probe_file()
    live: dict = {
        "generated_at": datetime.now().isoformat(),
        "chat_url": CHAT_URL,
        "new_chat": {}, "input": {}, "send": {}, "message": {},
        "upload_mode_select": {}, "attachment_card": {}, "response": {},
    }

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(DEFAULT_SESSION),
            headless=False,
            permissions=["clipboard-read", "clipboard-write"],
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            viewport={"width": 1280, "height": 800},
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(2500)
            page.screenshot(path=str(ART / "01_landing.png"))

            # 1) Auth
            url = page.url.lower()
            title = (page.title() or "").lower()
            auth_block = any(k in url or k in title for k in ("/login", "/signin", "just a moment", "cf-challenge"))
            live["session_logged_in"] = not auth_block
            if auth_block:
                print("  ⚠ Session expired/CAPTCHA. Resolve in the window, then re-run.")
                input("  ENTER after login: ")
                page.wait_for_timeout(2000)

            # 2) New Chat
            nc = _first_visible(page, NEW_CHAT_SELECTORS)
            live["new_chat"] = {"alive": nc is not None, "matched_selector": nc}
            print(f"  [{'PASS' if nc else 'FAIL'}] new_chat_button -> {nc}")
            if nc:
                page.locator(nc).first.click()
                page.wait_for_timeout(1200)
                page.screenshot(path=str(ART / "02_new_chat.png"))

            # 3) Input field
            inp = _first_visible(page, INPUT_SELECTORS)
            live["input"] = {"alive": inp is not None, "matched_selector": inp}
            print(f"  [{'PASS' if inp else 'FAIL'}] chat_input_field -> {inp}")
            if not inp:
                _dump(live)
                return 1
            page.screenshot(path=str(ART / "03_input.png"))

            # 4) Upload via mode-select (the only verified strategy)
            attached = False
            try:
                page.locator(".mode-select-open").first.click(timeout=5000)
                page.wait_for_timeout(500)
                item = page.locator(".mode-select-dropdown-item", has_text="Upload attachment").first
                if not item.is_visible(timeout=3000):
                    item = page.locator("text='Upload attachment'").first
                with page.expect_file_chooser(timeout=8000) as fc:
                    item.click()
                fc.value.set_files(str(probe))
                page.wait_for_timeout(1800)
                attached = bool(page.evaluate("""() => {
                    const s=['.file-card-list','.fileitem-btn','.message-input-column-file',
                             '[class*="file-card"]','[class*="file-item"]','[class*="fileitem"]'];
                    for(const sel of s){for(const el of document.querySelectorAll(sel)){
                        if(el.offsetWidth>0&&el.offsetHeight>0) return true;}}
                    return false;}"""))
            except Exception as e:
                live["upload_mode_select"]["error"] = str(e)[:200]
            live["upload_mode_select"]["alive"] = attached
            live["attachment_card"]["alive"] = attached
            print(f"  [{'PASS' if attached else 'FAIL'}] file_attachment (mode-select) -> {attached}")
            page.screenshot(path=str(ART / "04_attachment.png"))

            if attached:
                # 5) Inject (2-tier)
                target = page.locator(inp).first
                test_prompt = "Please confirm you received the attached file in one sentence."
                try:
                    target_handle = target.element_handle()
                    page.evaluate(
                        """([el, text]) => {
                            const proto = HTMLTextAreaElement.prototype;
                            const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                            if (setter) setter.call(el, text); else el.value = text;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }""",
                        [target_handle, test_prompt],
                    )
                    page.wait_for_timeout(800)
                    filled = page.evaluate(
                        "(el) => (el.value || el.innerText || '').trim()", target_handle
                    )
                    injected = bool(filled and test_prompt[:20] in filled)
                    live["prompt_injection"] = {"alive": injected, "chars": len(filled or "")}
                    print(f"  [{'PASS' if injected else 'FAIL'}] prompt_injection (React setter) -> {len(filled or '')} chars")
                except Exception as e:
                    live["prompt_injection"] = {"alive": False, "error": str(e)[:200]}
                    print(f"  [FAIL] prompt_injection -> {e}")
                page.screenshot(path=str(ART / "05_injected.png"))

                # 6) Send
                send = _first_visible(page, SEND_SELECTORS)
                live["send"] = {"alive": send is not None, "matched_selector": send}
                print(f"  [{'PASS' if send else 'FAIL'}] send_button -> {send}")
                page.screenshot(path=str(ART / "06_send.png"))

                if send:
                    # Mirror production: wait for file parsing to finish before sending
                    try:
                        page.wait_for_function("""() => {
                            const wait=['parsing','uploading','processing','please wait'];
                            for(const el of document.querySelectorAll('*')){
                                const r=el.getBoundingClientRect();
                                if(r.width===0||r.height===0) continue;
                                const t=(el.innerText||'').toLowerCase();
                                if(wait.some(k=>t.includes(k))) return false;
                            }
                            return true;
                        }""", timeout=120000)
                    except Exception:
                        pass
                    baseline = page.evaluate("""() => document.querySelectorAll(
                        '.markdown-body,[class*="message-content"],[class*="response"]').length""")
                    try:
                        page.locator(send).first.click()
                        print("  [PASS] send_clicked")
                    except Exception as e:
                        live["send"]["click_error"] = str(e)[:200]
                        print(f"  [FAIL] send_clicked -> {e}")
                    page.wait_for_timeout(45000)
                    resp = page.evaluate("""(baseline) => {
                        const s=['.chat-message-assistant .markdown-body','[class*="assistant"] .markdown-body',
                                 '[data-role="assistant"]','.qwen-markdown','.markdown-body',
                                 '[class*="message-content"]','[class*="message-body"]','[class*="response"]'];
                        for(const sel of s){const n=Array.from(document.querySelectorAll(sel)).filter(el=>{
                            const u=el.closest("[class*='user'],[class*='human'],[class*='prompt'],[class*='file-card']");
                            return !u;}); if(n.length){return (n[n.length-1].innerText||'').trim();}}
                        return '';}""", baseline)
                    live["response"] = {"alive": bool(resp), "chars": len(resp or "")}
                    print(f"  [{'PASS' if resp else 'FAIL'}] response_received -> {len(resp or '')} chars")
                    page.screenshot(path=str(ART / "07_response.png"))
                    if resp:
                        (ART / "probe_response.txt").write_text(resp, encoding="utf-8")

            _dump(live)
            summary = live.get("_summary", {})
            print(f"\nSummary: {summary}")
            input("\nProbe finished. ENTER to close the browser window: ")
            return 0
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def _dump(live: dict) -> None:
    total = passed = 0
    for key in ("session_logged_in", "new_chat", "input", "upload_mode_select",
                "attachment_card", "prompt_injection", "send", "response"):
        v = live.get(key)
        if isinstance(v, dict):
            ok = v.get("alive")
        else:
            ok = v
        if ok is True or ok is False:
            total += 1
            passed += 1 if ok else 0
    live["_summary"] = {"total": total, "passed": passed, "failed": total - passed}
    out = ART / f"selectors_live_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(live, indent=2, ensure_ascii=False), encoding="utf-8")
    # also keep a stable name for quick diffs
    (ART / "selectors_live.json").write_text(json.dumps(live, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSnapshot: {out}")


if __name__ == "__main__":
    sys.exit(main())
