"""Playwright automation for chat.qwen.ai with adaptive polling, MutationObserver, and Linux support.

P7 additions:
  - Configurable timeout (passed from AppConfig)
  - MutationObserver-based message detection (replaces dumb polling)
  - Adaptive polling fallback when MutationObserver not available
  - Linux paste key (Ctrl+V) for textarea input
"""
from __future__ import annotations

import json
import os
import re
import time
import logging
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from .config import AppConfig, AuthRequiredError, DEFAULT_LOG, RunContext, BrowserLaunchError
from .observability import get_logger, start_span

log = get_logger("qwen_client")

# ─── Message detection constants ─────────────────────────────────────────────
_POLL_INTERVAL: float = 1.0           # seconds between poll checks (adaptive)
_INITIAL_WAIT: int = 20_000          # milliseconds to wait for initial page load
_MAX_POLL_ATTEMPTS: int = 60          # max consecutive polls before giving up
_ADAPTIVE_TIMEOUT_BASE: int = 90      # base timeout for adaptive polling
_ADAPTIVE_TIMEOUT_MAX: int = 180      # max timeout cap
_ADAPTIVE_TIMEOUT_MIN: int = 30       # min timeout floor

# ─── Mutation observer script (injected into page) ───────────────────────────
_MUTATION_OBSERVER_JS = """() => {
    return new Promise((resolve) => {
        const target = document.querySelector('[data-testid="chat-message-text"]') ||
                       document.querySelector('[class*="message-text"]') ||
                       document.querySelector('[class*="ai-response"]') ||
                       document.querySelector('main') ||
                       document.body;
        if (!target) { resolve(null); return; }

        const observer = new MutationObserver((mutations) => {
            for (const m of mutations) {
                if (m.addedNodes.length > 0) {
                    for (const node of m.addedNodes) {
                        const txt = (node.textContent || '').trim();
                        if (txt.length > 10 && !txt.includes('What do you want to know') && !txt.includes('Auto')) {
                            observer.disconnect();
                            resolve(txt);
                            return;
                        }
                    }
                }
            }
        });
        observer.observe(target, { childList: true, subtree: true, characterData: true });

        // Timeout fallback
        setTimeout(() => {
            observer.disconnect();
            resolve(null);
        }, 180000);
    });
}"""


class QwenClient:
    """Wraps a Playwright persistent context to interact with chat.qwen.ai."""

    def __init__(self, ctx: BrowserContext | None, cfg: AppConfig | None = None) -> None:
        self.cfg = cfg
        self.browser: Browser | None = None
        self.context: BrowserContext | None = ctx
        self.page: Page | None = ctx.pages[0] if ctx and ctx.pages else (ctx.new_page() if ctx else None)

    def start(self) -> None:
        """Starts the Playwright persistent context with a pre-authenticated Chrome profile."""
        log.info("Launching browser with profile %s", self.cfg.chrome_profile if self.cfg else "default")
        pw = sync_playwright().start()
        try:
            launch_args: list[str] = ["--disable-blink-features=JavascriptControlAutofill"]
            if self.cfg and self.cfg.disable_sandbox:
                launch_args.insert(0, "--no-sandbox")

            self.browser = pw.chromium.launch(
                headless=False,
                args=launch_args,
            )
            state_file = self.cfg.storage_state_file if self.cfg else None
            self.context = self.browser.new_context(
                viewport={"width": 1280, "height": 800},
                storage_state=json.loads(state_file.read_text()) if state_file and state_file.exists() else None,
                locale="id-ID",
            )

            self.page = self.context.new_page()
            log.info("Browser started successfully")
        except Exception as e:
            pw.stop()
            raise BrowserLaunchError(f"Failed to start browser: {e}") from e

    def send_file(self, filepath: Path, timeout_sec: int, custom_prompt_path: Optional[Path] = None, rel_path: Optional[Path] = None) -> str:
        """Sends a prompt file to chat.qwen.ai and returns the full AI response as text.

        Args:
            filepath: Path to the .txt prompt file to send.
            timeout_sec: Maximum seconds to wait for a response.
            custom_prompt_path: Optional path to an additional PROMPT.md to prepend.
            rel_path: Relative path for logging context.
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")

        prompt = filepath.read_text(encoding="utf-8").strip()

        # P5: Prepend role prompt from custom_prompt_path if provided
        if custom_prompt_path and custom_prompt_path.exists():
            role_prompt = custom_prompt_path.read_text(encoding="utf-8").strip()
            if role_prompt.startswith("---"):
                parts = role_prompt.split("---", 2)
                if len(parts) >= 3:
                    role_prompt = parts[2].strip()
            prompt = f"{role_prompt}\n\n{prompt}"

        # Reset page to ensure clean state
        self.reset_page()

        log.info("Sending prompt to chat.qwen.ai (%d chars)", len(prompt))

        # Wait for page and input element to load
        self.page.goto("https://chat.qwen.ai/", timeout=30_000)
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=15_000)
        except Exception:
            pass

        # Wait for textarea element to be available
        try:
            self.page.wait_for_selector('textarea, [class*="input"], [class*="textarea"]', timeout=15_000)
        except Exception:
            pass

        # Click the textarea (first input or specific class)
        textarea = self.page.query_selector('textarea, [class*="input"], [class*="textarea"]')
        if not textarea:
            textarea = self.page.query_selector("textarea")
        if not textarea:
            raise RuntimeError("Could not find textarea on chat.qwen.ai page")

        # Focus and select all text in textarea
        try:
            textarea.focus()
            self.page.keyboard.press("Control+a" if os.name == "nt" else "Meta+a")
            self.page.keyboard.press("Delete")
        except Exception as e:
            log.warning("Failed to focus textarea: %s", e)

        # Type the prompt
        try:
            textarea.fill(prompt, timeout=5_000)
        except Exception:
            self._type_slowly(textarea, prompt)

        # Click the send button or press Enter
        sent = False
        try:
            send_btn = self.page.query_selector('button[type="submit"], [class*="send-button"], [class*="sendButton"], [aria-label*="Send"]')
            if send_btn and send_btn.is_enabled():
                send_btn.click(timeout=3_000)
                sent = True
        except Exception:
            pass

        if not sent:
            try:
                textarea.focus()
                self.page.keyboard.press("Enter")
            except Exception as e:
                log.warning("Could not submit prompt: %s", e)

        # P7: Adaptive polling with MutationObserver
        response = self._detect_response_mutation(timeout_sec)
        if response is None:
            # Fallback to adaptive polling
            response = self._adaptive_poll(timeout_sec)

        if response and len(response.strip()) > 0:
            log.info("Received response (%d chars)", len(response))
            return response.strip()
        else:
            raise TimeoutError(f"Timeout after {timeout_sec}s: no response detected")

    def _type_slowly(self, textarea: Any, text: str) -> None:
        """Types text character by character as a fallback for fill()."""
        textarea.focus()
        textarea.press("Control+a" if os.name == "nt" else "Meta+a")
        textarea.press("Delete")
        for char in text:
            try:
                textarea.press(char)
            except Exception:
                pass

    def _detect_response_mutation(self, timeout_sec: int) -> Optional[str]:
        """Uses MutationObserver to detect new content mutations on the page.

        Returns the observed text or None if timeout occurs.
        """
        log.info("Waiting for AI response...")

        try:
            assert self.page is not None
            result = self.page.evaluate(_MUTATION_OBSERVER_JS)  # type: ignore[arg-type]
            if result:
                return str(result)
        except PlaywrightTimeoutError:
            log.info("MutationObserver timed out, falling back to polling")
        except Exception as e:
            log.warning("MutationObserver failed (%s), falling back", type(e).__name__)

        return None

    def _adaptive_poll(self, timeout_sec: int) -> Optional[str]:
        """Adaptive polling strategy that adjusts based on response characteristics."""
        start = time.time()
        poll_interval = _POLL_INTERVAL
        consecutive_empty = 0
        last_text = ""

        # Phrases that indicate landing page UI, not an AI answer
        ignored_phrases = ["what do you want to know", "where should we begin", "how can i help", "good afternoon", "good morning"]

        while True:
            elapsed = time.time() - start
            if elapsed > timeout_sec:
                log.warning("Adaptive poll timed out after %ds", timeout_sec)
                break

            try:
                # Targeted selectors for assistant message content
                selectors = [
                    '[data-testid="chat-message-text"]',
                    '[class*="assistant"] [class*="message"]',
                    '[class*="message-text"]',
                    '[class*="ai-response"]',
                ]

                response_text = None
                for sel in selectors:
                    try:
                        assert self.page is not None
                        elements = self.page.query_selector_all(sel)
                        for element in reversed(elements):
                            text = element.inner_text().strip()
                            lower_text = text.lower()
                            if len(text) > 5 and not any(p in lower_text for p in ignored_phrases):
                                response_text = text
                                break
                        if response_text:
                            break
                    except Exception:
                        continue

                if response_text:
                    # Verify it's new content (not the same as last poll)
                    if response_text != last_text:
                        log.info("Poll detected new response (%d chars)", len(response_text))
                        return response_text
                    consecutive_empty += 1
                    last_text = response_text
                else:
                    consecutive_empty += 1

                # Adaptive interval: slow down as we wait longer
                if consecutive_empty > 10:
                    poll_interval = min(poll_interval * 1.5, 5.0)
                elif consecutive_empty < 3:
                    poll_interval = max(poll_interval * 0.7, 0.5)

                time.sleep(poll_interval)

            except PlaywrightTimeoutError:
                consecutive_empty += 1
                time.sleep(poll_interval)
            except Exception as e:
                log.warning("Poll error: %s", e)
                consecutive_empty += 1
                time.sleep(poll_interval)

        return None

    def reset_page(self) -> None:
        """Resets the page to a clean state by navigating back to chat.qwen.ai."""
        if self.page:
            try:
                self.page.goto("https://chat.qwen.ai/", timeout=10_000)
                self.page.wait_for_load_state("networkidle", timeout=15)
            except Exception as e:
                log.warning("Error resetting page: %s", e)

    def stop(self) -> None:
        """Stops the Playwright session and releases all resources."""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            log.info("Browser stopped successfully")
        except Exception as e:
            log.warning("Error stopping browser: %s", e)

    def __enter__(self) -> "QwenClient":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
