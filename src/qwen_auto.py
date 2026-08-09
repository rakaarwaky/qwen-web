#!/usr/bin/env python3
"""
qwen-cli v4: Production-grade automation for chat.qwen.ai.
Combines recursive folder support, contenteditable injection, and atomic queueing.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, List, Tuple

from playwright.sync_api import BrowserContext, Locator, Page, sync_playwright, Error as PlaywrightError

log = logging.getLogger("qwen-cli")

# ─── paths & defaults ────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).resolve().parent.parent
DEFAULT_TODO    = BASE_DIR / "input"
DEFAULT_PROC    = BASE_DIR / "input" / ".processing"
DEFAULT_DONE    = BASE_DIR / "input" / "done"
DEFAULT_FAILED  = BASE_DIR / "input" / "failed"
DEFAULT_OUTPUT  = BASE_DIR / "output"
DEFAULT_LOG     = BASE_DIR / "log"
DEFAULT_SESSION = BASE_DIR / "qwen_session"
CHAT_URL        = "https://chat.qwen.ai/"

# ─── DOM Selectors ───────────────────────────────────────────────────────────
NEW_CHAT_SELECTORS = (
    "button[aria-label*='New chat' i]", "button[aria-label*='Chat baru' i]",
    "button:has-text('New Chat')", "button:has-text('Chat Baru')",
)
INPUT_SELECTORS = (
    "textarea", "div[contenteditable='true']",
    "[placeholder*='Ask' i]", "[placeholder*='Message' i]", "[placeholder*='Ketik' i]",
    "#chat-input", ".chat-input",
)
SEND_SELECTORS = (
    "button[aria-label*='Send' i]:not([disabled])",
    "button[aria-label*='Kirim' i]:not([disabled])",
    "button[type='submit']:not([disabled])",
    "button[class*='send']:not([disabled])",
    "button[id*='send']:not([disabled])",
)
MESSAGE_SELECTORS = (
    ".chat-message-assistant .markdown-body",
    "[class*='assistant'] .markdown-body",
    ".markdown-body",
    "[class*='message-content']",
    "[class*='response']",
)


# ─── config & exceptions ─────────────────────────────────────────────────────
class AuthRequiredError(RuntimeError): pass
class PromptInjectionError(RuntimeError): pass

@dataclass(frozen=True)
class AppConfig:
    mode: str
    input_path: Path
    output_path: Path
    done_path: Path
    failed_path: Path
    proc_path: Path
    session_path: Path
    log_path: Path = DEFAULT_LOG
    interval: int = 3
    timeout: int = 300
    headless: bool = False
    prompt_file: Optional[Path] = None

@dataclass
class RunContext:
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6])


def load_role_prompt(file_path: Path, custom_prompt_path: Optional[Path] = None, rel_path: Optional[Path] = None) -> str:
    """Dynamically loads custom PROMPT.md from file's parent role directory in input/."""
    if custom_prompt_path and custom_prompt_path.exists() and custom_prompt_path.is_file():
        content = custom_prompt_path.read_text(encoding="utf-8").strip()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3: content = parts[2].strip()
        return content

    search_dirs: List[Path] = []

    if rel_path and rel_path.parts and rel_path.parts[0].startswith("role-"):
        role_dir_rel = DEFAULT_TODO / rel_path.parts[0]
        search_dirs.append(role_dir_rel)
        search_dirs.append(role_dir_rel.resolve())

    abs_path = file_path.resolve()
    curr_abs = abs_path.parent if abs_path.is_file() else abs_path
    search_dirs.append(curr_abs)
    search_dirs.extend(curr_abs.parents)

    curr_rel = file_path.parent if file_path.is_file() else file_path
    if curr_rel not in search_dirs:
        search_dirs.append(curr_rel)
        search_dirs.extend(curr_rel.parents)

    for path_obj in [abs_path, file_path]:
        for part in path_obj.parts:
            if part.startswith("role-"):
                role_dir_abs = DEFAULT_TODO.resolve() / part
                if role_dir_abs not in search_dirs:
                    search_dirs.append(role_dir_abs)
                role_dir_rel = DEFAULT_TODO / part
                if role_dir_rel not in search_dirs:
                    search_dirs.append(role_dir_rel)

    for p in search_dirs:
        prompt_file = p / "PROMPT.md"
        if prompt_file.exists() and prompt_file.is_file():
            content = prompt_file.read_text(encoding="utf-8").strip()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3: content = parts[2].strip()
            if content:
                log.info("Loaded role prompt from %s (%d chars)", prompt_file, len(content))
                return content
    return ""


# ─── browser lifecycle ───────────────────────────────────────────────────────
@contextmanager
def browser_session(cfg: AppConfig) -> Iterator[BrowserContext]:
    cfg.session_path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(cfg.session_path, 0o700)
    except Exception as e:
        log.debug("Failed setting session path permissions: %s", e)
    chrome_bin = "/usr/bin/google-chrome"
    kwargs = {
        "user_data_dir": str(cfg.session_path),
        "headless": cfg.headless,
        "permissions": ["clipboard-read", "clipboard-write"],
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
        "viewport": {"width": 1280, "height": 800},
    }
    if Path(chrome_bin).exists():
        kwargs["executable_path"] = chrome_bin

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(**kwargs)
        if cfg.mode != "login":
            # Abort heavy static assets directly by pattern to prevent IPC overhead on XHR/SSE requests
            ctx.route("**/*.{png,jpg,jpeg,gif,webp,mp4,mp3,woff,woff2,ttf,otf}", lambda r: r.abort())
        try: yield ctx
        finally:
            try: ctx.close()
            except Exception: pass


# ─── Qwen Client ─────────────────────────────────────────────────────────────
class QwenClient:
    def __init__(self, ctx: BrowserContext, headless: bool) -> None:
        self.ctx = ctx
        self.headless = headless
        self._page: Optional[Page] = None

    @property
    def page(self) -> Page:
        if self._page is None or self._page.is_closed():
            valid_pages = [p for p in self.ctx.pages if not p.is_closed()]
            self._page = valid_pages[0] if valid_pages else self.ctx.new_page()
        return self._page

    def reset_page(self) -> None:
        if self._page and not self._page.is_closed():
            try: self._page.close()
            except Exception: pass
        self._page = self.ctx.new_page()

    def _ensure_chat_page(self) -> None:
        if "chat.qwen.ai" not in self.page.url.lower():
            self.page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=60_000)
            self.page.wait_for_timeout(1500)

    def _wait_for_auth(self, timeout: int = 15) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try: title, url = self.page.title().lower(), self.page.url.lower()
            except Exception: return
            if any(k in title or k in url for k in ("just a moment", "cf-challenge", "login", "signin")):
                if self.headless:
                    raise AuthRequiredError(
                        "CAPTCHA/Login required but running in headless mode. "
                        "Run once without --headless to authenticate and save the session."
                    )
                log.warning("auth challenge detected — waiting for manual resolution")
                time.sleep(2)
                continue
            return
        raise TimeoutError("Auth challenge did not resolve within timeout.")

    def start_new_chat(self) -> None:
        self._ensure_chat_page()
        self._wait_for_auth()
        for sel in NEW_CHAT_SELECTORS:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=800):
                    btn.click()
                    self.page.wait_for_timeout(300)
                    return
            except PlaywrightError: continue

    def _find_input(self) -> Optional[Locator]:
        for sel in INPUT_SELECTORS:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=1500): return el
            except PlaywrightError: continue
        return None

    def _count_messages(self) -> int:
        try:
            return self.page.evaluate("""() => {
                const nodes = document.querySelectorAll(".markdown-body, [class*='message-content'], [class*='response']");
                const assistantNodes = Array.from(nodes).filter(el => {
                    const userParent = el.closest("[class*='user'], [class*='human'], [class*='prompt'], [class*='file-card']");
                    return !userParent;
                });
                return assistantNodes.length;
            }""")
        except PlaywrightError as e:
            log.debug("Playwright error counting messages: %s", e)
            return 0
        except Exception as e:
            log.warning("Unexpected error counting messages: %s", e)
            return 0

    def _latest_message_text(self, baseline: int) -> str:
        try:
            return self.page.evaluate("""(baseline) => {
                const nodes = document.querySelectorAll(".markdown-body, [class*='message-content'], [class*='response']");
                const assistantNodes = Array.from(nodes).filter(el => {
                    const userParent = el.closest("[class*='user'], [class*='human'], [class*='prompt'], [class*='file-card']");
                    return !userParent;
                });
                if (assistantNodes.length > 0) {
                    const lastNode = assistantNodes[assistantNodes.length - 1];
                    return (lastNode.innerText || "").trim();
                }
                return "";
            }""", baseline)
        except PlaywrightError as e:
            log.debug("Playwright error getting latest message: %s", e)
            return ""
        except Exception as e:
            log.warning("Unexpected error getting latest message: %s", e)
            return ""

    def _inject_text(self, target: Locator, text: str) -> None:
        errors: List[str] = []
        
        # Strategy 1: Native React injection (supports textarea, input, contenteditable)
        try:
            self.page.evaluate("""([el, text]) => {
                if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                    if (setter) setter.call(el, text); else el.value = text;
                } else {
                    el.innerText = text;
                }
                el.dispatchEvent(new Event('input',  { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", [target.element_handle(), text])
            return
        except Exception as e: errors.append(f"ReactInject: {e}")

        # Strategy 2: Playwright Fill
        try: target.fill(text); return
        except Exception as e: errors.append(f"PWFill: {e}")

        # Strategy 3: Clipboard
        try:
            self.page.evaluate(f"navigator.clipboard.writeText({json.dumps(text)})")
            self.page.keyboard.press("ControlOrMeta+v")
            return
        except Exception as e: errors.append(f"Clipboard: {e}")

        # Strategy 4: Raw Typing
        try: target.type(text, delay=0); return
        except Exception as e: errors.append(f"RawType: {e}")

        raise PromptInjectionError(f"All injection strategies failed: {' | '.join(errors)}")

    def _is_file_parsing_or_waiting(self) -> bool:
        """Checks if Qwen UI is displaying 'please wait', file uploading, or parsing indicators in DOM."""
        try:
            return self.page.evaluate("""() => {
                const waitKeywords = [
                    "parsing", "uploading", "processing", "please wait", "wait for file",
                    "file is processing", "file parsing", "sedang memproses", "mengunggah", "mohon tunggu", "tunggu"
                ];
                
                // 1. Check attachment DOM cards & file size elements (.fileitem-file-size, .file-card-list, etc.)
                const fileElements = document.querySelectorAll(
                    ".fileitem-file-size, .file-card-list, .fileitem-btn, .message-input-column-file, " +
                    ".file-content-info, [class*='file'], [class*='attachment'], [class*='toast'], [class*='notice'], " +
                    "[class*='message'], [class*='alert'], [role='alert'], .ant-message, .ant-message-notice"
                );
                for (const el of fileElements) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0) {
                        const txt = (el.innerText || "").toLowerCase();
                        if (waitKeywords.some(kw => txt.includes(kw))) {
                            return true;
                        }
                    }
                }
                
                // 2. Check loading spinners and animation elements inside container and file cards
                const loaders = document.querySelectorAll(
                    ".ant-spin, svg[class*='spin'], svg[class*='animate-spin'], [class*='loading'], " +
                    "[class*='uploading'], [class*='progress'], [data-status='uploading'], [data-status='parsing']"
                );
                for (const loader of loaders) {
                    if (loader.offsetWidth > 0 && loader.offsetHeight > 0) {
                        return true;
                    }
                }
                return false;
            }""")
        except PlaywrightError as e:
            log.debug("Playwright error checking parsing indicator: %s", e)
            return False
        except Exception as e:
            log.warning("Unexpected error checking parsing indicator: %s", e)
            return False

    def _wait_for_input_parsed(self, timeout: int = 120) -> None:
        """Waits for Qwen UI to finish parsing input & file attachments via Playwright wait_for_function."""
        js_condition = """(sendSelectors) => {
            const waitKeywords = [
                "parsing", "uploading", "processing", "please wait", "wait for file",
                "file is processing", "file parsing", "sedang memproses", "mengunggah", "mohon tunggu", "tunggu"
            ];
            
            const fileElements = document.querySelectorAll(
                ".fileitem-file-size, .file-card-list, .fileitem-btn, .message-input-column-file, " +
                ".file-content-info, [class*='file'], [class*='attachment'], [class*='toast'], [class*='notice'], " +
                "[class*='message'], [class*='alert'], [role='alert'], .ant-message, .ant-message-notice"
            );
            for (const el of fileElements) {
                if (el.offsetWidth > 0 && el.offsetHeight > 0) {
                    const txt = (el.innerText || "").toLowerCase();
                    if (waitKeywords.some(kw => txt.includes(kw))) return false;
                }
            }
            
            const loaders = document.querySelectorAll(
                ".ant-spin, svg[class*='spin'], svg[class*='animate-spin'], [class*='loading'], " +
                "[class*='uploading'], [class*='progress'], [data-status='uploading'], [data-status='parsing']"
            );
            for (const loader of loaders) {
                if (loader.offsetWidth > 0 && loader.offsetHeight > 0) return false;
            }
            
            for (const sel of sendSelectors) {
                const btns = document.querySelectorAll(sel);
                for (const b of btns) {
                    if (b.offsetWidth > 0 && b.offsetHeight > 0 && !b.disabled && b.getAttribute("aria-disabled") !== "true") {
                        return true;
                    }
                }
            }
            return false;
        }"""
        
        try:
            self.page.wait_for_function(js_condition, arg=list(SEND_SELECTORS), timeout=timeout * 1000)
            print("  ✅ [EVENT_DOCUMENT_PARSED] Dokumen selesai diproses Qwen")
        except PlaywrightError as e:
            log.debug("Playwright error waiting for input parsed: %s", e)
            raise TimeoutError("Timed out waiting for file attachment parsing to complete.")

    def _is_prompt_dispatched(self, baseline: int) -> bool:
        """Checks if the prompt has been dispatched and Qwen is generating or displaying messages."""
        try:
            if self._count_messages() > baseline:
                return True

            if "/c/" in self.page.url:
                return True

            is_active = self.page.evaluate("""(baseline) => {
                const stopBtn = document.querySelector(
                    "button[aria-label*='stop' i], button[aria-label*='Stop' i], " +
                    "button[class*='stop'], .message-input-right-button svg use[*|href*='stop']"
                );
                if (stopBtn && stopBtn.offsetWidth > 0) return true;

                const userMsgs = document.querySelectorAll("[class*='user-message'], [class*='message-item'], .markdown-body");
                if (userMsgs.length > baseline) return true;

                return false;
            }""", baseline)
            if is_active:
                return True
        except Exception:
            pass
        return False

    def _click_send(self, target: Locator, baseline: int) -> bool:
        """Dispatches prompt by clicking Send button or pressing Enter, verifying prompt dispatch state."""
        if self._is_prompt_dispatched(baseline):
            print("  📥 [EVENT_DISPATCH_ACKNOWLEDGED] Qwen menerima pesan")
            return True

        print("  🚀 [EVENT_SEND_CLICKED] Tombol kirim ditekan")
        for attempt in range(3):
            if self._is_file_parsing_or_waiting():
                try: self._wait_for_input_parsed(timeout=30)
                except Exception: pass

            clicked = False
            for sel in SEND_SELECTORS:
                try:
                    for btn in reversed(self.page.locator(sel).all()):
                        if btn.is_visible() and btn.is_enabled():
                            btn.click()
                            clicked = True
                            break
                    if clicked: break
                except PlaywrightError: continue
            
            if not clicked:
                try:
                    target.focus()
                    self.page.keyboard.press("Enter")
                    clicked = True
                except PlaywrightError: pass

            if clicked:
                # Wait up to 10 seconds for dispatch state to register
                deadline = time.time() + 10
                while time.time() < deadline:
                    if self._is_prompt_dispatched(baseline):
                        print("  📥 [EVENT_DISPATCH_ACKNOWLEDGED] Qwen menerima pesan")
                        return True
                    time.sleep(0.5)

                if ui_err := self._check_ui_error():
                    raise RuntimeError(f"Qwen UI validation error: {ui_err}")

        is_ack = self._is_prompt_dispatched(baseline)
        if is_ack:
            print("  📥 [EVENT_DISPATCH_ACKNOWLEDGED] Qwen menerima pesan")
        return is_ack

    def _is_network_disconnected(self) -> bool:
        """Detects if Qwen web UI displays a visible network error or reconnecting overlay banner."""
        try:
            return self.page.evaluate("""() => {
                const toastEls = document.querySelectorAll(".ant-message-warning, .ant-message-error, [class*='offline-banner'], [class*='network-error']");
                for (const el of toastEls) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0) {
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                        const text = (el.innerText || "").toLowerCase().trim();
                        if (text.length > 0 && ["reconnecting", "network error", "connection lost", "failed to fetch", "connection error"].some(k => text.includes(k))) {
                            return true;
                        }
                    }
                }
                return false;
            }""")
        except PlaywrightError as e:
            log.debug("Playwright error checking network disconnected: %s", e)
            return False
        except Exception as e:
            log.warning("Unexpected error checking network disconnected: %s", e)
            return False

    def _wait_for_response(self, baseline: int, timeout: int) -> str:
        deadline = time.time() + timeout
        last, stable = "", 0
        thinking_logged = False
        reconnect_attempts = 0
        max_reconnects = 5
        
        while time.time() < deadline:
            if reconnect_attempts < max_reconnects and not last and self._is_network_disconnected():
                reconnect_attempts += 1
                print(f"\n  🔄 [EVENT_NETWORK_RECONNECTING] Koneksi terputus ({reconnect_attempts}/{max_reconnects}). Menunggu pemulihan koneksi stream server Qwen...")
                time.sleep(2)
                if reconnect_attempts >= max_reconnects:
                    try:
                        self.page.reload(wait_until="domcontentloaded", timeout=15000)
                        self.page.wait_for_timeout(2000)
                    except Exception as e:
                        log.warning("Page reload during reconnection failed: %s", e)
                continue

            if not thinking_logged:
                print("  🧠 [EVENT_THINKING_STARTED] Qwen sedang berpikir...")
                thinking_logged = True

            current = self._latest_message_text(baseline)
            if current and current == last:
                stable += 1
                if stable >= 3:
                    print("\n  🎉 [EVENT_GENERATION_FINISHED] Qwen sudah selesai mengetik hasilnya")
                    return current
            else:
                stable, last = 0, current
                if current:
                    print(f"\r  ✍️ [EVENT_STREAMING_GENERATION] Qwen sedang mengetik hasilnya ({len(current):,} Karakter)...", end="", flush=True)
            time.sleep(1.0)
        print("\n  🎉 [EVENT_GENERATION_FINISHED] Qwen selesai (timeout reached)")
        return last or ""

    def _check_ui_error(self) -> Optional[str]:
        error_selectors = (
            ".ant-message-error", ".el-message--error", "[class*='toast']",
            "[class*='notification']", "[role='alert']", ".error-message",
            "[class*='error']"
        )
        try:
            return self.page.evaluate("""(selectors) => {
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    for (const el of els) {
                        const t = (el.innerText || "").trim();
                        const lower = t.toLowerCase();
                        if (["reconnect", "network error", "connection lost", "failed to fetch"].some(k => lower.includes(k))) {
                            continue;
                        }
                        if (t && ["cannot", "exceed", "more than", "limit", "too long", "too large", "char"].some(k => lower.includes(k))) {
                            return t;
                        }
                    }
                }
                return null;
            }""", list(error_selectors))
        except Exception:
            return None

    def _upload_file_attachment(self, file_path: Path) -> bool:
        """Uploads file to Qwen chat via direct file input #filesUpload or dropdown menu, verifying attachment registration in DOM."""
        # Method 1: Try direct set_input_files on hidden input #filesUpload
        try:
            file_input = self.page.locator("#filesUpload").first
            if file_input.count() > 0:
                file_input.set_input_files(str(file_path))
                self.page.wait_for_timeout(1000)
                # Verify attachment card created in DOM (.file-card-list or .fileitem-btn)
                card_exists = self.page.evaluate("""() => {
                    return document.querySelectorAll(".file-card-list, .fileitem-btn, .message-input-column-file").length > 0;
                }""")
                if card_exists:
                    print("  📎 [EVENT_DOCUMENT_ATTACHED] Dokumen berhasil di-inputkan ke area lampiran")
                    return True
        except Exception as e:
            log.debug("Direct #filesUpload attachment failed, trying dropdown fallback: %s", e)

        # Method 2: Fallback via '+' button (.mode-select-open) & dropdown file chooser
        plus_selectors = (
            ".mode-select-open",
            "[aria-label='Select Mode']",
            ".mode-select",
            "button:has-text('+')",
        )

        plus_btn = None
        for sel in plus_selectors:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=1000):
                    plus_btn = el
                    break
            except Exception: continue

        if not plus_btn:
            log.warning("Could not locate '+' button (.mode-select-open)")
            return False

        try:
            plus_btn.click()
            self.page.wait_for_timeout(500)

            item_selectors = (
                "li[data-menu-id*='upload']",
                ".mode-select-common-item:has-text('Upload attachment')",
                "li[role='menuitem']:has-text('Upload attachment')",
                "span:has-text('Upload attachment')",
                "text='Upload attachment'",
            )

            upload_item = None
            for item_sel in item_selectors:
                try:
                    item = self.page.locator(item_sel).first
                    if item.is_visible(timeout=1000):
                        upload_item = item
                        break
                except Exception: continue

            if not upload_item:
                log.warning("Could not locate 'Upload attachment' menu item in dropdown")
                return False

            with self.page.expect_file_chooser(timeout=8000) as fc_info:
                upload_item.click()

            file_chooser = fc_info.value
            file_chooser.set_files(str(file_path))
            self.page.wait_for_timeout(1000)
            print("  📎 [EVENT_DOCUMENT_ATTACHED] Dokumen berhasil di-inputkan ke area lampiran")
            return True
        except Exception as e:
            log.warning("File chooser upload failed: %s", e)
            return False

    def send_file(self, file_path: Path, timeout: int, custom_prompt_path: Optional[Path] = None, rel_path: Optional[Path] = None) -> str:
        self.start_new_chat()
        target = self._find_input()
        if not target: raise RuntimeError("could not locate Qwen chat input")

        baseline = self._count_messages()
        prompt_content = file_path.read_text(encoding="utf-8").strip()

        # Step 1: Upload File Attachment
        uploaded = self._upload_file_attachment(file_path)
        if not uploaded:
            print("  📝 Direct text injection fallback...")

        # Step 2: Wait for Qwen UI frontend to finish uploading & parsing document
        self._wait_for_input_parsed(timeout=120)

        # Step 3: Inject prompt text AFTER file parsing completes
        role_prompt = load_role_prompt(file_path, custom_prompt_path, rel_path=rel_path)
        if uploaded:
            if role_prompt:
                prompt_instruction = (
                    f"Berikut adalah instruksi peran (role-based prompt) yang WAJIB Anda ikuti dalam menganalisis:\n\n"
                    f"{role_prompt}\n\n"
                    f"---\n"
                    f"Tolong analisa dan proses file terlampir `{file_path.name}` ini sesuai dengan instruksi peran di atas."
                )
            else:
                prompt_instruction = f"Tolong analisa dan proses file terlampir `{file_path.name}` ini."
            try:
                self._inject_text(target, prompt_instruction)
                print(f"  ✍️ [EVENT_PROMPT_INJECTED] Prompt instruksi peran (role-based: {len(role_prompt):,} chars) berhasil ditulis")
            except Exception: pass
        else:
            if role_prompt:
                prompt_content = f"{role_prompt}\n\n---\n\n{prompt_content}"
            self._inject_text(target, prompt_content)
            print("  ✍️ [EVENT_PROMPT_INJECTED] Prompt isi dokumen berhasil ditulis")

        self.page.wait_for_timeout(1000)

        if ui_err := self._check_ui_error():
            raise RuntimeError(f"Qwen UI validation error: {ui_err}")

        if not self._click_send(target, baseline):
            if ui_err := self._check_ui_error():
                raise RuntimeError(f"Qwen UI validation error: {ui_err}")
            raise RuntimeError("failed to dispatch prompt (Send button disabled or missing)")

        text = self._wait_for_response(baseline, timeout)
        if not text or len(text.strip()) < 20:
            raise RuntimeError(f"Qwen response too short or empty ({len(text)} chars)")
        return text

    def send_prompt(self, prompt: str, timeout: int) -> str:
        self.start_new_chat()
        target = self._find_input()
        if not target: raise RuntimeError("could not locate Qwen chat input")

        baseline = self._count_messages()
        self._inject_text(target, prompt)
        
        # Wait for Qwen UI frontend to finish parsing the long document (Send button enabled)
        print("  ⏳ Waiting for Qwen UI to finish parsing document...", end="", flush=True)
        self._wait_for_input_parsed(timeout=30)
        print("\r                                                        \r", end="", flush=True)

        if ui_err := self._check_ui_error():
            raise RuntimeError(f"Qwen UI validation error: {ui_err}")

        if not self._click_send(target, baseline):
            if ui_err := self._check_ui_error():
                raise RuntimeError(f"Qwen UI validation error: {ui_err}")
            raise RuntimeError("failed to dispatch prompt (Send button disabled or missing)")

        text = self._wait_for_response(baseline, timeout)
        if not text: raise TimeoutError("Qwen response timed out or was empty")
        return text


# ─── Audit & Filesystem ──────────────────────────────────────────────────────
class AuditLog:
    def __init__(self, log_dir: Optional[Path] = None) -> None:
        target_dir = log_dir or DEFAULT_LOG
        target_dir.mkdir(parents=True, exist_ok=True)
        self._audit = target_dir / "audit_history.jsonl"
        self._errors = target_dir / "errors.log"

    def log(self, status: str, ctx: RunContext, src: str, dst: str, dur: float, in_c: int, out_c: int, err: str = "") -> None:
        rec = {"run_id": ctx.run_id, "timestamp": datetime.now().isoformat(), "source_file": src, "output_file": dst,
               "status": status, "duration_sec": dur, "input_chars": in_c, "output_chars": out_c}
        if err: rec["error"] = err
        with self._audit.open("a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if err:
            with self._errors.open("a", encoding="utf-8") as f: f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {src}: {err}\n\n")

def _write_output(path: Path, content: str, ctx: RunContext, src: str, dur: float, in_c: int, out_c: int) -> None:
    header = (
        "<!--\n"
        "--- METADATA TRACEABILITY ---\n"
        f"Run ID           : {ctx.run_id}\n"
        f"Source File      : {src}\n"
        f"Processed At     : {datetime.now().isoformat()}\n"
        f"Duration         : {dur:.2f}s\n"
        f"Input Characters : {in_c}\n"
        f"Output Characters: {out_c}\n"
        "-----------------------------\n"
        "-->\n\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + content, encoding="utf-8")
    print(f"  📋 [EVENT_OUTPUT_COPIED] Output berhasil disalin ke file {path.name}")


def resolve_role_paths(rel_path: Path, cfg: AppConfig) -> tuple[Path, Path, Path, Path]:
    """
    Resolves role-based paths for output, done, failed, and processing.
    If rel_path starts with a role folder (e.g. role-architect), stores done/.processing/failed inside that role folder!
    Returns (out_path, done_path, fail_path, proc_file).
    """
    parts = rel_path.parts
    if parts and parts[0].startswith("role-"):
        role_folder = parts[0]
        sub_parts = parts[1:]
        if sub_parts and sub_parts[0] == "todo":
            sub_parts = sub_parts[1:]
        sub_path = Path(*sub_parts) if sub_parts else Path(rel_path.name)
        
        out_path = cfg.output_path / role_folder / sub_path
        done_path = DEFAULT_TODO / role_folder / "done" / sub_path
        fail_path = DEFAULT_TODO / role_folder / "failed" / sub_path
        proc_file = DEFAULT_TODO / role_folder / ".processing" / sub_path
    else:
        sub_parts = parts
        if sub_parts and sub_parts[0] == "todo":
            sub_parts = sub_parts[1:]
        sub_path = Path(*sub_parts) if sub_parts else Path(rel_path.name)

        out_path = cfg.output_path / sub_path if not (cfg.mode == "single" and cfg.output_path.suffix) else cfg.output_path
        done_path = cfg.done_path / sub_path
        fail_path = cfg.failed_path / sub_path
        proc_file = cfg.proc_path / sub_path

    return out_path, done_path, fail_path, proc_file


# ─── Unified Pipeline (Atomic Queue with Subfolder Support) ──────────────────
def _iter_todo(cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
    """Yield (proc_file, relative_path) tuples."""
    
    if cfg.mode == "single":
        if not cfg.input_path.exists(): raise FileNotFoundError(cfg.input_path)
        try:
            rel_path = cfg.input_path.resolve().relative_to(DEFAULT_TODO.resolve())
        except ValueError:
            abs_p = cfg.input_path.resolve()
            parts = abs_p.parts
            role_idx = next((i for i, part in enumerate(parts) if part.startswith("role-")), None)
            if role_idx is not None:
                rel_path = Path(*parts[role_idx:])
            else:
                rel_path = Path(cfg.input_path.name)
        _, _, _, proc_file = resolve_role_paths(rel_path, cfg)
        proc_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cfg.input_path, proc_file)
        yield proc_file, rel_path
        return

    src = cfg.input_path if cfg.input_path.is_dir() else DEFAULT_TODO
    src.mkdir(parents=True, exist_ok=True)
    cfg.proc_path.mkdir(parents=True, exist_ok=True)

    skip_dirs = {"done", "failed", ".processing", "proc"}

    def _should_process(f: Path) -> bool:
        if not f.is_file(): return False
        if f.name.startswith(".") or f.name.upper() == "PROMPT.MD": return False
        rel_parts = f.resolve().relative_to(src.resolve()).parts
        if any(p in skip_dirs or p.startswith(".") for p in rel_parts[:-1]): return False
        return True

    if cfg.mode == "batch":
        for f in sorted(f for f in src.rglob("*") if _should_process(f)):
            rel_path = f.resolve().relative_to(src.resolve())
            _, _, _, proc_dest = resolve_role_paths(rel_path, cfg)
            proc_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(proc_dest))
            yield proc_dest, rel_path
        return

    # Watcher mode - recursive with rglob
    log.info("watching %s every %ds", src, cfg.interval)
    while True:
        for f in sorted(f for f in src.rglob("*") if _should_process(f)):
            rel_path = f.resolve().relative_to(src.resolve())
            _, _, _, proc_dest = resolve_role_paths(rel_path, cfg)
            proc_dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(f), str(proc_dest))
                yield proc_dest, rel_path
            except OSError as e:
                log.debug("skipping %s: %s", f, e)
        time.sleep(cfg.interval)

def _process_file(client: QwenClient, proc_file: Path, rel_path: Path, 
                  cfg: AppConfig, audit: AuditLog, ctx: RunContext) -> None:
    out_path, done_path, fail_path, _ = resolve_role_paths(rel_path, cfg)
    
    prompt = proc_file.read_text(encoding="utf-8").strip()
    print(f"• {rel_path} ({len(prompt):,} chars)")
    t0 = time.time()
    
    last_err: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            text = client.send_file(proc_file, cfg.timeout, custom_prompt_path=cfg.prompt_file, rel_path=rel_path)
            dur = time.time() - t0
            _write_output(out_path, text, ctx, str(rel_path), dur, len(prompt), len(text))
            audit.log("SUCCESS", ctx, str(rel_path), str(out_path), dur, len(prompt), len(text))
            
            # Move to done (preserve subfolder structure), avoiding overwriting out_path if out_path == done_path
            if out_path.resolve() == done_path.resolve():
                try: proc_file.unlink()
                except Exception: pass
            else:
                done_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(proc_file), str(done_path))
            print(f"  -> {out_path} ({dur:.1f}s)")
            return
        except Exception as e:
            last_err = e
            log.warning("attempt %d/3 for %s failed: %s", attempt, rel_path, e)
            client.reset_page()
            if attempt < 3: time.sleep(2 * attempt)

    # Max retries exhausted -> Quarantine (preserve subfolder structure)
    dur = time.time() - t0
    err_msg = f"{type(last_err).__name__}: {last_err}"
    audit.log("FAILED", ctx, str(rel_path), str(out_path), dur, len(prompt), 0, err_msg)
    
    if out_path.resolve() != fail_path.resolve():
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(proc_file), str(fail_path))
    else:
        try: proc_file.unlink()
        except Exception: pass
    print(f"  x QUARANTINED to {fail_path}: {last_err}")


# ─── CLI & Interactive Fallback ──────────────────────────────────────────────
def _run_manual_login(cfg: AppConfig) -> None:
    login_cfg = AppConfig(
        mode="login", input_path=cfg.input_path, output_path=cfg.output_path,
        done_path=cfg.done_path, failed_path=cfg.failed_path, proc_path=cfg.proc_path,
        session_path=cfg.session_path, interval=cfg.interval, timeout=cfg.timeout, headless=False
    )
    print(f"\n🔑 [Manual Login] Launching visible browser window on {CHAT_URL}...")
    with browser_session(login_cfg) as bctx:
        page = bctx.pages[0] if bctx.pages else bctx.new_page()
        page.goto(CHAT_URL, wait_until="domcontentloaded")
        print("👉 Please log in or resolve CAPTCHA in the browser window.")
        input("👉 Press [ENTER] here once you have finished logging in: ")
        print(f"✅ Session data successfully saved to '{login_cfg.session_path}'. You can now run in headless mode!\n")

def _list_input_files(src: Path) -> List[Tuple[Path, Path]]:
    """List processable files in input directory as (absolute_path, relative_path) tuples."""
    skip_dirs = {"done", "failed", ".processing", "proc"}
    files: List[Tuple[Path, Path]] = []
    if not src.exists() or not src.is_dir():
        return files
    for f in sorted(f for f in src.rglob("*") if f.is_file()):
        if f.name.startswith(".") or f.name.upper() == "PROMPT.MD":
            continue
        rel_parts = f.relative_to(src).parts
        if any(p in skip_dirs or p.startswith(".") for p in rel_parts[:-1]):
            continue
        files.append((f, f.relative_to(src)))
    return files

def _interactive_prompt() -> AppConfig:
    print("\n╭─ qwen-cli interactive setup ─────────────────────╮")
    print("│ 1. Watcher Mode (continuous)                     │")
    print("│ 2. Batch Mode (folder)                           │")
    print("│ 3. Single File Mode                              │")
    print("│ 4. Manual Login / Session Setup                  │")
    print("│ 5. Exit                                          │")
    print("╰──────────────────────────────────────────────────╯")
    
    choice = input("Select [1-5, default=1]: ").strip() or "1"
    if choice == "5":
        print("Goodbye!")
        sys.exit(0)
    
    if choice == "4":
        return AppConfig(
            mode="login", input_path=DEFAULT_TODO, output_path=DEFAULT_OUTPUT,
            done_path=DEFAULT_DONE, failed_path=DEFAULT_FAILED, proc_path=DEFAULT_PROC,
            session_path=DEFAULT_SESSION, headless=False
        )
    
    headless = input("Run headless? [y/N, default=N]: ").strip().lower() == "y"
    
    mode = {"1": "watcher", "2": "batch", "3": "single"}.get(choice, "watcher")
    
    if mode == "single":
        available_files = _list_input_files(DEFAULT_TODO)
        if available_files:
            print("\n📁 Available input files:")
            for idx, (abs_p, rel_p) in enumerate(available_files, 1):
                print(f"  {idx}. {rel_p}")
            
            file_choice = input(f"Select input file [1-{len(available_files)}, default=1]: ").strip() or "1"
            try:
                choice_idx = int(file_choice) - 1
                if 0 <= choice_idx < len(available_files):
                    chosen_abs, chosen_rel = available_files[choice_idx]
                else:
                    chosen_abs, chosen_rel = available_files[0]
            except ValueError:
                chosen_abs, chosen_rel = available_files[0]
            
            return AppConfig(
                mode=mode, input_path=chosen_abs, output_path=DEFAULT_OUTPUT / chosen_rel,
                done_path=DEFAULT_DONE, failed_path=DEFAULT_FAILED, proc_path=DEFAULT_PROC,
                session_path=DEFAULT_SESSION, headless=headless
            )
        else:
            input_file = input("Enter input file path [default: input.md]: ").strip() or "input.md"
            output_file = input("Enter output file path [default: output.md]: ").strip() or "output.md"
            return AppConfig(
                mode=mode, input_path=Path(input_file), output_path=Path(output_file),
                done_path=DEFAULT_DONE, failed_path=DEFAULT_FAILED, proc_path=DEFAULT_PROC,
                session_path=DEFAULT_SESSION, headless=headless
            )
    
    return AppConfig(
        mode=mode, input_path=DEFAULT_TODO, output_path=DEFAULT_OUTPUT,
        done_path=DEFAULT_DONE, failed_path=DEFAULT_FAILED, proc_path=DEFAULT_PROC,
        session_path=DEFAULT_SESSION, headless=headless
    )

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="qwen-cli", description="Automate chat.qwen.ai")
    p.add_argument("-i", "--input", default=str(DEFAULT_TODO))
    p.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT))
    p.add_argument("-d", "--done-dir", default=str(DEFAULT_DONE))
    p.add_argument("--failed-dir", default=str(DEFAULT_FAILED))
    p.add_argument("--proc-dir", default=str(DEFAULT_PROC))
    p.add_argument("--log-dir", default=str(DEFAULT_LOG))
    p.add_argument("-w", "--watch", action="store_true")
    p.add_argument("--interval", type=int, default=3)
    p.add_argument("--headless", action="store_true", help="Run browser headlessly (default: show window)")
    p.add_argument("--data-dir", default=str(DEFAULT_SESSION))
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--login", action="store_true", help="Open browser to log in manually and save session")
    return p.parse_args()

def _build_config(args: argparse.Namespace) -> AppConfig:
    if getattr(args, "login", False): mode = "login"
    elif getattr(args, "watch", False): mode = "watcher"
    else:
        input_path = Path(args.input)
        if input_path.is_dir() or not input_path.suffix: mode = "batch"
        else: mode = "single"
    return AppConfig(
        mode=mode, input_path=Path(args.input), output_path=Path(args.output),
        done_path=Path(args.done_dir), failed_path=Path(args.failed_dir), proc_path=Path(args.proc_dir),
        session_path=Path(args.data_dir), log_path=Path(getattr(args, "log_dir", str(DEFAULT_LOG))),
        interval=getattr(args, "interval", 3), timeout=getattr(args, "timeout", 300), headless=getattr(args, "headless", False)
    )

def main() -> int:
    cfg = _interactive_prompt() if len(sys.argv) == 1 else _build_config(_parse_args())
    cfg.log_path.mkdir(parents=True, exist_ok=True)

    log_file = cfg.log_path / "qwen_cli.log"
    file_h = logging.FileHandler(log_file, encoding="utf-8")
    stream_h = logging.StreamHandler(sys.stdout)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[file_h, stream_h])
    
    if cfg.mode == "login":
        _run_manual_login(cfg)
        return 0

    ctx = RunContext()
    audit = AuditLog(cfg.log_path)

    try:
        with browser_session(cfg) as bctx:
            client = QwenClient(bctx, cfg.headless)
            for proc_file, rel_path in _iter_todo(cfg):
                _process_file(client, proc_file, rel_path, cfg, audit, ctx)
    except AuthRequiredError as e:
        log.error("Auth blocked: %s", e)
        return 2
    except KeyboardInterrupt:
        print("\n[interrupted]")
        return 130
    except Exception as e:
        log.exception("fatal error")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
