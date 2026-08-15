"""Ad-hoc probe: open Qwen, attach file, send, and dump DOM + screenshot state."""
from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SESSION = ROOT / ".qwen-web" / "qwen_session"
OUT = ROOT / "tests" / "artifacts"
OUT.mkdir(parents=True, exist_ok=True)

prompt = ROOT / ".qwen-web" / "input" / "test_upload_prompt.md"
if not prompt.exists():
    prompt = ROOT / ".qwen-web" / "input" / "test_upload_prompt.md"
    prompt.write_text("# Test\nConfirm you received this attached file.\n", encoding="utf-8")


def dump(page, tag: str) -> None:
    try:
        html = page.content()
        (OUT / f"{tag}_dom.html").write_text(html, encoding="utf-8")
    except Exception as exc:
        print(f"[{tag}] dump failed: {exc}")
    try:
        page.screenshot(path=str(OUT / f"{tag}_screen.png"), full_page=True)
    except Exception as exc:
        print(f"[{tag}] screenshot failed: {exc}")


def main() -> None:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(SESSION),
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
            viewport={"width": 1280, "height": 800},
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto("https://chat.qwen.ai/", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            dump(page, "01_loaded")

            # open mode select
            try:
                page.click(".mode-select-open", timeout=5000)
            except Exception as exc:
                print("mode-select-open click failed:", exc)
            page.wait_for_timeout(500)
            dump(page, "02_dropdown")

            # click upload attachment - try multiple selector strategies
            upload_item = None
            for selector in ["text=Upload attachment", ".mode-select-dropdown-item:has-text('Upload attachment')",
                            ".mode-select-dropdown-item[data-action='upload']", "[role='menuitem']:has-text('Upload attachment')",
                            "text=Upload file", "[data-testid*='upload' i]", "[aria-label*='upload' i]"]:
                try:
                    upload_item = page.locator(selector).first
                    if upload_item.count() > 0 and upload_item.is_visible(timeout=100):
                        print(f"Found upload attachment using selector: {selector}")
                        break
                except Exception:
                    continue
            if upload_item is None:
                print("Could not find upload attachment option")
            else:
                with page.expect_file_chooser(timeout=8000) as fc:
                    upload_item.click()
                fc.value.set_files(str(prompt))
            page.wait_for_timeout(4000)
            dump(page, "03_attached")

            # wait for attachment card parse ready
            for _ in range(40):
                try:
                    status = page.locator(".message-input-column-file .fileitem-file-size").last.inner_text(timeout=200)
                except Exception:
                    status = ""
                print("att status:", status)
                if status and "parsing" not in status.lower():
                    break
                page.wait_for_timeout(500)
            dump(page, "04_parse_ready")

            # inject prompt
            try:
                ta = page.locator("textarea.message-input-textarea").first
                ta.fill("")
                ta.type("Confirm you received this attached file.", timeout=5000)
            except Exception as exc:
                print("inject failed:", exc)
            dump(page, "05_injected")

            # click send
            try:
                page.click("button[aria-label*='Send' i]", timeout=5000)
            except Exception as exc:
                print("send click failed:", exc)
            page.wait_for_timeout(2000)
            dump(page, "06_sent")

            # poll for user turn
            for i in range(20):
                try:
                    cnt = page.evaluate("""() => {
                        return document.querySelectorAll(
                            '.chat-response-message, [class*="chat-message"], ' +
                            '[class*="message-item"], [class*="virtual-list-item"], ' +
                            '[class*="turn"], .markdown-body'
                        ).length;
                    }""")
                except Exception:
                    cnt = -1
                print(f"poll {i}: turn_count={cnt}")
                page.wait_for_timeout(1000)
            dump(page, "07_after_send")
        finally:
            ctx.close()


if __name__ == "__main__":
    main()