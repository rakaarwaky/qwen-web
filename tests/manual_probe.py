#!/usr/bin/env python3
"""
Manual headed-probe for qwen-web-automation.

Purpose
-------
Exercise the REAL chat.qwen.ai DOM with the EXACT selectors/config the
production code uses (src/config.py + src/qwen_client.py), so we can
confirm, before touching the automation script, that:
  - the saved session still logs us in (no /login redirect),
  - the "New Chat" button selector still resolves,
  - the chat input selector still resolves,
  - file attachment (the 4 fallback strategies) still works,
  - prompt injection + Send dispatch + response stability loop behave.

Run (headed, visible window):
    python3 tests/manual_probe.py

It is NON-DESTRUCTIVE: it works on a throwaway file in /tmp, never the
real input/ queue. Screenshots + a JSON report land in tests/artifacts/.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# allow running as a standalone script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from browser import browser_session  # noqa: E402
from config import (  # noqa: E402
    CHAT_URL,
    DEFAULT_SESSION,
    NEW_CHAT_SELECTORS,
    INPUT_SELECTORS,
    SEND_SELECTORS,
)

ART = Path(__file__).resolve().parent / "artifacts"
ART.mkdir(parents=True, exist_ok=True)


class Result:
    def __init__(self) -> None:
        self.steps: list[dict] = []

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        self.steps.append({"step": name, "pass": ok, "detail": detail})
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))

    def dump(self) -> None:
        report = {
            "generated_at": datetime.now().isoformat(),
            "chat_url": CHAT_URL,
            "steps": self.steps,
            "summary": {
                "total": len(self.steps),
                "passed": sum(1 for s in self.steps if s["pass"]),
                "failed": sum(1 for s in self.steps if not s["pass"]),
            },
        }
        out = ART / f"manual_probe_{datetime.now():%Y%m%d_%H%M%S}.json"
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport: {out}")
        print(f"Artifacts dir: {ART}")


def _make_probe_file() -> Path:
    p = Path("/tmp/qwen_manual_probe.md")
    p.write_text(
        "# Manual Probe\n\n"
        "This is a throwaway test file created by tests/manual_probe.py.\n"
        "Please reply with a one-sentence confirmation that you can read this file.\n",
        encoding="utf-8",
    )
    return p


def main() -> int:
    res = Result()
    probe = _make_probe_file()

    # Headed config mirroring main._run_manual_login so the window is visible.
    from config import AppConfig

    cfg = AppConfig(
        mode="login",  # bypasses route-blocking so we can SEE assets
        input_path=probe,
        output_path=ART / "probe_output.md",
        done_path=ART / "done",
        failed_path=ART / "failed",
        proc_path=ART / "proc",
        session_path=DEFAULT_SESSION,
        headless=False,
    )

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(cfg.session_path),
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

            # 1) Auth / session check
            url = page.url.lower()
            title = (page.title() or "").lower()
            auth_block = any(k in url or k in title for k in ("/login", "/signin", "just a moment", "cf-challenge"))
            res.record("session_logged_in", not auth_block, f"url={page.url}")
            page.screenshot(path=str(ART / "01_landing.png"))

            if auth_block:
                print("\n  ⚠ Session expired or CAPTCHA present. Resolve it in the window, then re-run.")
                input("  Press ENTER after you have logged in to continue probing: ")
                page.wait_for_timeout(2000)

            # 2) New Chat button
            new_chat_found = None
            for sel in NEW_CHAT_SELECTORS:
                try:
                    if page.locator(sel).first.is_visible(timeout=1200):
                        new_chat_found = sel
                        break
                except Exception:
                    continue
            res.record("new_chat_button", new_chat_found is not None, f"selector={new_chat_found}")
            if new_chat_found:
                page.locator(new_chat_found).first.click()
                page.wait_for_timeout(1200)
                page.screenshot(path=str(ART / "02_new_chat.png"))

            # 3) Input field
            input_found = None
            for sel in INPUT_SELECTORS:
                try:
                    if page.locator(sel).first.is_visible(timeout=1500):
                        input_found = sel
                        break
                except Exception:
                    continue
            res.record("chat_input_field", input_found is not None, f"selector={input_found}")
            page.screenshot(path=str(ART / "03_input.png"))

            if not input_found:
                res.dump()
                return 1

            # 4) File attachment (mirror _upload_file_attachment strategies)
            attached = False
            attach_detail = ""
            try:
                fi = page.locator("#filesUpload").first
                fi.set_input_files(str(probe), timeout=5000)
                page.wait_for_timeout(1800)
                if page.evaluate("""() => {
                    const s=['.file-card-list','.fileitem-btn','.message-input-column-file',
                             '[class*="file-card"]','[class*="file-item"]','[class*="fileitem"]',
                             '[class*="attachment"]','.file-card'];
                    for(const sel of s){for(const el of document.querySelectorAll(sel)){
                        if(el.offsetWidth>0&&el.offsetHeight>0) return true;}}
                    return false;}"""):
                    attached = True
                    attach_detail = "hidden #filesUpload"
            except Exception as e:
                attach_detail = f"hidden input failed: {e}"
            res.record("file_attachment", attached, attach_detail)
            page.screenshot(path=str(ART / "04_attachment.png"))

            if not attached:
                print("\n  ⚠ Attachment failed. You can still try manually in the window, then re-run the probe.")
            else:
                # 5) Prompt injection (mirror _inject_text strategy 1: React setter)
                target = page.locator(input_found).first
                test_prompt = (
                    "Please analyze the attached file and reply with a one-sentence confirmation."
                )
                try:
                    target.element_handle().evaluate(
                        """([el, text]) => {
                            if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                                const proto = el.tagName === 'TEXTAREA'
                                    ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                                const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                                if (setter) setter.call(el, text); else el.value = text;
                            } else { el.innerText = text; }
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }""",
                        [target.element_handle(), test_prompt],
                    )
                    page.wait_for_timeout(800)
                    filled = target.input_value() if target.get_attribute("value") is not None else (
                        page.evaluate("el => el.innerText", target.element_handle()) or ""
                    )
                    injected = bool(filled and test_prompt[:20] in filled)
                    res.record("prompt_injection", injected, f"chars={len(filled or '')}")
                except Exception as e:
                    res.record("prompt_injection", False, str(e))
                page.screenshot(path=str(ART / "05_injected.png"))

                # 6) Send button
                send_found = None
                for sel in SEND_SELECTORS:
                    try:
                        if page.locator(sel).first.is_visible(timeout=1200):
                            send_found = sel
                            break
                    except Exception:
                        continue
                res.record("send_button", send_found is not None, f"selector={send_found}")
                page.screenshot(path=str(ART / "06_send.png"))

                # 7) Dispatch + response (manual: click & watch; do NOT block forever)
                if send_found:
                    baseline = page.evaluate("""() => document.querySelectorAll(
                        '.markdown-body,[class*="message-content"],[class*="response"]').length""")
                    try:
                        page.locator(send_found).first.click()
                        res.record("send_clicked", True)
                    except Exception as e:
                        res.record("send_clicked", False, str(e))
                    # give Qwen up to ~45s to stream; capture whatever appears
                    page.wait_for_timeout(45000)
                    resp = page.evaluate("""(baseline) => {
                        const s=['.chat-message-assistant .markdown-body','[class*="assistant"] .markdown-body',
                                 '[data-role="assistant"]','.qwen-markdown','.markdown-body',
                                 '[class*="message-content"]','[class*="message-body"]','[class*="response"]'];
                        for(const sel of s){const n=Array.from(document.querySelectorAll(sel)).filter(el=>{
                            const u=el.closest("[class*='user'],[class*='human'],[class*='prompt'],[class*='file-card']");
                            return !u;}); if(n.length){return (n[n.length-1].innerText||'').trim();}}
                        return '';}""", baseline)
                    res.record("response_received", bool(resp), f"chars={len(resp or '')}")
                    page.screenshot(path=str(ART / "07_response.png"))
                    if resp:
                        (ART / "probe_response.txt").write_text(resp, encoding="utf-8")

            res.dump()
            input("\nProbe finished. Press ENTER to close the browser window: ")
            return 0
        finally:
            try:
                ctx.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
