"""Qwen web client automation handler and DOM interactor."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Optional

from playwright.sync_api import BrowserContext, Locator, Page, Error as PlaywrightError

try:
    from .config import CHAT_URL, INPUT_SELECTORS, NEW_CHAT_SELECTORS, SEND_SELECTORS, AuthRequiredError, PromptInjectionError
    from .observability import get_logger, start_span
except ImportError:
    from config import CHAT_URL, INPUT_SELECTORS, NEW_CHAT_SELECTORS, SEND_SELECTORS, AuthRequiredError, PromptInjectionError
    from observability import get_logger, start_span

log = get_logger("qwen_client")


class QwenClient:
    """Production-grade Web Client interface for chat.qwen.ai."""

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
            try:
                self._page.close()
            except Exception:
                pass
        self._page = self.ctx.new_page()

    def _ensure_chat_page(self) -> None:
        if "chat.qwen.ai" not in self.page.url.lower():
            self.page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=60_000)
            self.page.wait_for_timeout(1500)

    def _wait_for_auth(self, timeout: int = 15) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                title, url = self.page.title().lower(), self.page.url.lower()
            except Exception:
                return
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
            except PlaywrightError:
                continue

    def _find_input(self) -> Optional[Locator]:
        for sel in INPUT_SELECTORS:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=1500):
                    return el
            except PlaywrightError:
                continue
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
            res = self.page.evaluate("""(baseline) => {
                const selectors = [
                    ".chat-message-assistant .markdown-body",
                    "[class*='assistant'] .markdown-body",
                    "[data-role='assistant']",
                    ".qwen-markdown",
                    ".markdown-body",
                    "[class*='message-content']",
                    "[class*='message-body']",
                    "[class*='response']"
                ];
                for (const sel of selectors) {
                    const nodes = Array.from(document.querySelectorAll(sel)).filter(el => {
                        const userParent = el.closest("[class*='user'], [class*='human'], [class*='prompt'], [class*='file-card']");
                        return !userParent;
                    });
                    if (nodes.length > 0) {
                        const lastNode = nodes[nodes.length - 1];
                        const text = (lastNode.innerText || "").trim();
                        if (text.length > 0) return text;
                    }
                }
                return "";
            }""", baseline)
            return res if isinstance(res, str) else ""
        except PlaywrightError as e:
            log.debug("Playwright error getting latest message: %s", e)
            return ""
        except Exception as e:
            log.warning("Unexpected error getting latest message: %s", e)
            return ""

    def _inject_text(self, target: Locator, text: str) -> None:
        # Two-tier injection, validated against the live Qwen UI (Qwen3.8-Max):
        #   Tier 1 — native React value setter + synthetic input/change events
        #           (most reliable for React-controlled <textarea.message-input-textarea>).
        #   Tier 2 — clipboard write + Ctrl/Cmd+V paste (covers contenteditable / edge cases).
        # Playwright fill() and raw type() were removed: fill() does not trigger React
        # state updates, and type() is O(n) slow for 100k+ char prompts.
        errors: List[str] = []

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
        except Exception as e:
            errors.append(f"ReactInject: {e}")

        try:
            self.page.evaluate(f"navigator.clipboard.writeText({json.dumps(text)})")
            self.page.keyboard.press("ControlOrMeta+v")
            return
        except Exception as e:
            errors.append(f"Clipboard: {e}")

        raise PromptInjectionError(f"All injection strategies failed: {' | '.join(errors)}")

    def _is_file_parsing_or_waiting(self) -> bool:
        """Checks if Qwen UI is displaying 'please wait', file uploading, or parsing indicators in DOM."""
        try:
            return self.page.evaluate("""() => {
                const waitKeywords = [
                    "parsing", "uploading", "processing", "please wait", "wait for file",
                    "file is processing", "file parsing"
                ];
                
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
                "file is processing", "file parsing"
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
            print("  ✅ [EVENT_DOCUMENT_PARSED] Document parsed by Qwen")
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
                    "button[class*='stop'], .message-input-button svg use[*|href*='stop']"
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
            print("  📥 [EVENT_DISPATCH_ACKNOWLEDGED] Qwen received the message")
            return True

        print("  🚀 [EVENT_SEND_CLICKED] Send button pressed")
        for attempt in range(3):
            if self._is_file_parsing_or_waiting():
                try:
                    self._wait_for_input_parsed(timeout=30)
                except Exception:
                    pass

            clicked = False
            for sel in SEND_SELECTORS:
                try:
                    for btn in reversed(self.page.locator(sel).all()):
                        if btn.is_visible() and btn.is_enabled():
                            btn.click()
                            clicked = True
                            break
                    if clicked:
                        break
                except PlaywrightError:
                    continue
            
            if not clicked:
                try:
                    target.focus()
                    self.page.keyboard.press("Enter")
                    clicked = True
                except PlaywrightError:
                    pass

            if clicked:
                deadline = time.time() + 10
                while time.time() < deadline:
                    if self._is_prompt_dispatched(baseline):
                        print("  📥 [EVENT_DISPATCH_ACKNOWLEDGED] Qwen received the message")
                        return True
                    time.sleep(0.5)

                if ui_err := self._check_ui_error():
                    raise RuntimeError(f"Qwen UI validation error: {ui_err}")

        is_ack = self._is_prompt_dispatched(baseline)
        if is_ack:
            print("  📥 [EVENT_DISPATCH_ACKNOWLEDGED] Qwen received the message")
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
        with start_span("wait_for_response") as span:
            if span is not None:
                span.set_attribute("timeout_sec", timeout)
                span.set_attribute("baseline_messages", baseline)
            result = self._wait_for_response_inner(baseline, timeout)
            if span is not None:
                span.set_attribute("output_chars", len(result))
            return result

    def _wait_for_response_inner(self, baseline: int, timeout: int) -> str:
        deadline = time.time() + timeout
        last, stable = "", 0
        thinking_logged = False
        reconnect_attempts = 0
        max_reconnects = 5
        
        while time.time() < deadline:
            if reconnect_attempts < max_reconnects and not last and self._is_network_disconnected():
                reconnect_attempts += 1
                print(f"\n  🔄 [EVENT_NETWORK_RECONNECTING] Connection lost ({reconnect_attempts}/{max_reconnects}). Reloading the page to restore the Qwen server stream...")
                try:
                    self.page.wait_for_timeout(1000)
                    self.page.reload(wait_until="domcontentloaded", timeout=15000)
                    self.page.wait_for_timeout(1000)
                except Exception as e:
                    log.warning("Page reload during reconnection failed: %s", e)
                continue

            if not thinking_logged:
                print("  🧠 [EVENT_THINKING_STARTED] Qwen is thinking...")
                thinking_logged = True

            current = self._latest_message_text(baseline)
            if current and current == last:
                stable += 1
                if stable >= 3:
                    print("\n  🎉 [EVENT_GENERATION_FINISHED] Qwen finished generating the response")
                    return current
            else:
                stable, last = 0, current
                if current:
                    print(f"\r  ✍️ [EVENT_STREAMING_GENERATION] Qwen is typing its response ({len(current):,} chars)...", end="", flush=True)
            time.sleep(1.0)
        print("\n  🎉 [EVENT_GENERATION_FINISHED] Qwen finished (timeout reached)")
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
        except PlaywrightError as e:
            log.debug("Playwright error checking UI error: %s", e)
            return None
        except Exception as e:
            log.warning("Unexpected error checking UI error: %s", e)
            return None

    def _verify_attachment_in_dom(self, file_name: str = "") -> bool:
        """Verifies that an uploaded file attachment card is visibly registered in Qwen's input DOM."""
        try:
            for _ in range(12):
                card_exists = self.page.evaluate("""(fileName) => {
                    const selectors = [
                        '.file-card-list', '.fileitem-btn', '.message-input-column-file',
                        '[class*="file-card"]', '[class*="file-item"]', '[class*="fileitem"]',
                        '[class*="attachment"]', '[class*="upload"]', '.file-card'
                    ];
                    for (const sel of selectors) {
                        const els = document.querySelectorAll(sel);
                        for (const el of els) {
                            if (el.offsetWidth > 0 && el.offsetHeight > 0) return true;
                        }
                    }
                    if (fileName && (document.body.innerText || "").includes(fileName)) return true;
                    return false;
                }""", file_name)
                if card_exists:
                    return True
                self.page.wait_for_timeout(300)
            return False
        except Exception:
            return False

    def _upload_file_attachment(self, file_path: Path) -> bool:
        """Uploads a file to Qwen chat via the '+' (mode-select) attachment menu.

        Validated against the live Qwen UI (Qwen3.8-Max): the only working path is
        clicking `.mode-select-open` and selecting the "Upload attachment" dropdown
        item, which opens a native file chooser. The legacy `#filesUpload` hidden
        input and JS DataTransfer strategies are dead against the current UI (they no
        longer render an attachment card), so they were removed to cut dead code.
        """
        try:
            self.page.locator(".mode-select-open").first.click(timeout=5000)
            self.page.wait_for_timeout(500)
            upload_item = self.page.locator(
                ".mode-select-dropdown-item", has_text="Upload attachment"
            ).first
            if not upload_item.is_visible(timeout=3000):
                upload_item = self.page.locator("text='Upload attachment'").first
            with self.page.expect_file_chooser(timeout=8000) as fc_info:
                upload_item.click()
            fc_info.value.set_files(str(file_path))
            self.page.wait_for_timeout(1500)
            if self._verify_attachment_in_dom(file_path.name):
                print("  📎 [EVENT_DOCUMENT_ATTACHED] File attached via mode-select menu")
                return True
            log.warning(
                "mode-select upload set files but no attachment card appeared",
                file=file_path.name,
            )
        except Exception as e:
            log.warning("mode-select upload failed: %s", e)
        return False

    def send_file(self, file_path: Path, timeout: int, custom_prompt_path: Optional[Path] = None, rel_path: Optional[Path] = None) -> str:
        with start_span("send_file") as span:
            if span is not None:
                span.set_attribute("file_name", file_path.name)
                span.set_attribute("timeout_sec", timeout)
                span.set_attribute("rel_path", str(rel_path) if rel_path else "")
            try:
                from .pipeline import load_role_prompt
            except ImportError:
                from pipeline import load_role_prompt

            self.start_new_chat()
            target = self._find_input()
            if not target:
                raise RuntimeError("could not locate Qwen chat input")

            baseline = self._count_messages()

            uploaded = self._upload_file_attachment(file_path)
            if not uploaded:
                raise RuntimeError(f"Failed to upload file '{file_path.name}' via the attachment button. Input files MUST be uploaded through the attachment button!")

            self._wait_for_input_parsed(timeout=120)

            role_prompt = load_role_prompt(file_path, custom_prompt_path, rel_path=rel_path)
            if role_prompt:
                prompt_instruction = (
                    f"Below are role-based instructions you MUST follow when analyzing:\n\n"
                    f"{role_prompt}\n\n"
                    f"---\n"
                    f"Please analyze and process the attached file `{file_path.name}` according to the role instructions above."
                )
            else:
                prompt_instruction = f"Please analyze and process the attached file `{file_path.name}`."

            self._inject_text(target, prompt_instruction)
            print(f"  ✍️ [EVENT_PROMPT_INJECTED] Role-based instruction prompt (role: {len(role_prompt):,} chars) written successfully")

            self.page.wait_for_timeout(1000)

            if ui_err := self._check_ui_error():
                raise RuntimeError(f"Qwen UI validation error: {ui_err}")

            if not self._click_send(target, baseline):
                if ui_err := self._check_ui_error():
                    raise RuntimeError(f"Qwen UI validation error: {ui_err}")
                raise RuntimeError("failed to dispatch prompt (Send button disabled or missing)")

            text = self._wait_for_response(baseline, timeout)
            if not text:
                raise TimeoutError("Qwen response timed out or was empty")
            if span is not None:
                span.set_attribute("output_chars", len(text))
            return text

    def send_prompt(self, prompt: str, timeout: int) -> str:
        with start_span("send_prompt") as span:
            if span is not None:
                span.set_attribute("prompt_chars", len(prompt))
                span.set_attribute("timeout_sec", timeout)
            self.start_new_chat()
            target = self._find_input()
            if not target:
                raise RuntimeError("could not locate Qwen chat input")

            baseline = self._count_messages()
            self._inject_text(target, prompt)
            print("  ✍️ [EVENT_PROMPT_INJECTED] Document prompt written successfully")
            self.page.wait_for_timeout(1000)

            if ui_err := self._check_ui_error():
                raise RuntimeError(f"Qwen UI validation error: {ui_err}")

            if not self._click_send(target, baseline):
                if ui_err := self._check_ui_error():
                    raise RuntimeError(f"Qwen UI validation error: {ui_err}")
                raise RuntimeError("failed to dispatch prompt (Send button disabled or missing)")

            text = self._wait_for_response(baseline, timeout)
            if not text:
                raise TimeoutError("Qwen response timed out or was empty")
            if span is not None:
                span.set_attribute("output_chars", len(text))
            return text
