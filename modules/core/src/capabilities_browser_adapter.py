"""Browser lifecycle capability (Playwright adaptation).

Capabilities layer: implements IBrowserProtocol. Imports taxonomy, contract(protocol),
utility only. Logger obtained via structlog (external), not via another capability.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import structlog
from playwright.sync_api import (
    BrowserContext,
    Error,
    Page,
    Playwright,
    sync_playwright,
)
from tenacity import RetryCallState, Retrying, stop_after_attempt, wait_fixed

from modules.shared.src.contract_core_protocol import IBrowserProtocol
from modules.shared.src.taxonomy_core_constant import (
    AUTH_KEYWORDS,
    CHAT_URL,
    LOGIN_FORM_SELECTORS,
    TEXTAREA_SELECTOR,
)
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_vo import (
    EVENT_NETWORK_RECONNECTING,
    EVENT_WEB_LOADED,
)
from modules.shared.src.taxonomy_domain_error import AuthRequiredError, BrowserLaunchError

log = structlog.get_logger("browser")

# Block 1: Class Definition & Constructor

class SessionCheck:
    """Validates that the browser session and Qwen chat UI are alive."""

    def __init__(self, page: Page) -> None:
        """Initialize with a Playwright Page instance."""
        self.page = page

    # ─── Block 2: Public Contract (IBrowserProtocol ONLY) ──

    def is_alive(self) -> bool:
        """Return True if the session is stable and the chat UI is responsive."""
        try:
            ready = self.page.evaluate("() => document.readyState")
            if ready != "complete":
                log.warning("session_check_failed", reason="page_not_ready", ready=ready)
                return False

            if not self.page.query_selector(TEXTAREA_SELECTOR):
                log.warning("session_check_failed", reason="textarea_missing")
                return False

            return True
        except Error as exc:
            log.warning("session_check_failed", reason="playwright_error", error=str(exc))
            return False
        except Exception as exc:
            log.warning("session_check_failed", reason="unexpected_error", error=str(exc))
            return False

    def check_auth(self) -> None:
        """Raise AuthRequiredError if the session is no longer authenticated or UI is missing."""
        try:
            _assert_on_chat_page(self.page)
        except AuthRequiredError:
            raise
        except Error as exc:
            raise AuthRequiredError(f"Session invalid (browser error): {exc}") from exc

# Block 3: Dunder Methods, Factories & Helpers


    def __repr__(self) -> str:
        """Return string representation of SessionCheck."""
        return f"SessionCheck(page={self.page!r})"


def _assert_on_chat_page(page: Page) -> None:
    """Raise AuthRequiredError if the page is a login/auth page (URL + DOM triple-check)."""
    current_url = page.url.lower()

    if any(k in current_url for k in AUTH_KEYWORDS):
        raise AuthRequiredError(
            f"Not authenticated — browser is on login page ({page.url}). "
            "Run 'python3 src/main.py --login' to save your session first."
        )

    if not page.query_selector(TEXTAREA_SELECTOR):
        for sel in LOGIN_FORM_SELECTORS:
            try:
                if page.locator(sel).count() > 0:
                    raise AuthRequiredError(
                        f"Not authenticated — login form detected ({sel}). "
                        "Run 'python3 src/main.py --login' to save your session first."
                    )
            except AuthRequiredError:
                raise
            except Error:
                continue
        log.warning("chat_textarea_missing_but_no_login_form_detected", url=page.url)


# Block 1: Class Definition & Constructor


class BrowserAdapter(IBrowserProtocol):
    """Persistent Chromium browser context adapter implementing the browser contract."""

    def __init__(self) -> None:
        """Initialize BrowserAdapter."""
        pass

# Block 2: Public Contract


    def reset_page(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Reset the page to a clean state by navigating back to chat.qwen.ai."""
        try:
            emitter.emit(EVENT_NETWORK_RECONNECTING, {"url": CHAT_URL})
            page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=10_000)
            page.wait_for_load_state("domcontentloaded", timeout=15_000)
        except Error as e:
            log.warning("Failed to reset page: %s", e)

    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate to chat.qwen.ai, emit WEB_LOADED, and verify authenticated session."""
        page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=30_000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15_000)
        except Error as e:
            log.warning("Load state wait failed, proceeding: %s", e)
        _assert_on_chat_page(page)
        emitter.emit(EVENT_WEB_LOADED, {"url": page.url})

    def check_auth(self, page: Page) -> None:
        """Raise AuthRequiredError if the page is on a login/auth URL or login form detected."""
        _assert_on_chat_page(page)

    def _clean_stale_locks(self, user_data_dir: str) -> None:
        """Clean up stale Chromium lock files if process crashed or before launch."""
        session_path = Path(user_data_dir)
        for fname in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            lock_path = session_path / fname
            try:
                if lock_path.is_symlink() or lock_path.exists():
                    lock_path.unlink(missing_ok=True)
            except OSError as e:
                log.warning("Failed to delete stale lock %s: %s", lock_path, e)

    def _launch_context(self, p: Playwright, kwargs: dict[str, Any]) -> BrowserContext:
        """Launch the persistent context with tenacity retry for transient crashes."""
        user_data_dir = kwargs.get("user_data_dir", "")
        if user_data_dir:
            self._clean_stale_locks(user_data_dir)

        def _before_sleep(retry_state: RetryCallState) -> None:
            sleep_val = retry_state.next_action.sleep if retry_state.next_action else 2
            if user_data_dir:
                self._clean_stale_locks(user_data_dir)
            log.warning(
                "browser_launch_failed_retrying",
                attempt=retry_state.attempt_number,
                next_wait_sec=sleep_val,
                error=str(retry_state.outcome.exception()) if retry_state.outcome else "unknown",
            )

        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_fixed(2),
            before_sleep=_before_sleep,
            reraise=True,
        ):
            with attempt:
                ctx = p.chromium.launch_persistent_context(**kwargs)
                return ctx

        raise RuntimeError("browser launch failed after retries")  # pragma: no cover

    @contextmanager
    def browser_session(self, cfg: Any) -> Iterator[BrowserContext]:
        """Manage persistent Chromium browser context with session caching and asset optimization."""
        cfg.session_path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(cfg.session_path, 0o644)
        except OSError as e:
            log.debug("failed_setting_session_permissions", error=str(e))

        chrome_bin = (
            shutil.which("google-chrome")
            or shutil.which("google-chrome-stable")
            or shutil.which("chromium")
            or shutil.which("chromium-browser")
            or ""
        )

        chrome_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ]

        if cfg.headless:
            chrome_args.extend([
                "--disable-gpu",
                "--disable-software-compositing",
            ])

        kwargs: dict[str, Any] = {
            "user_data_dir": str(cfg.session_path),
            "headless": cfg.headless,
            "permissions": ["clipboard-read", "clipboard-write"],
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "args": chrome_args,
            "viewport": {"width": 1280, "height": 800},
        }

        if chrome_bin and Path(chrome_bin).exists():
            kwargs["executable_path"] = chrome_bin

        try:
            if hasattr(asyncio, "_set_running_loop"):
                asyncio._set_running_loop(None)
        except (RuntimeError, AttributeError):
            pass

        try:
            with sync_playwright() as p:
                ctx = self._launch_context(p, kwargs)
                if cfg.mode != "login":
                    ctx.route(
                        "**/*.{png,jpg,jpeg,gif,webp,mp4,mp3,woff,woff2,ttf,otf}",
                        lambda r: r.abort(),
                    )
                try:
                    yield ctx
                finally:
                    try:
                        ctx.close()
                    except Error as e:
                        log.warning("Error closing browser context: %s", e)
        except AuthRequiredError:
            raise
        except Exception as e:
            log.critical("browser_launch_failed", error=str(e))
            raise BrowserLaunchError(f"Failed to launch browser: {e}") from e

# Block 3: Dunder Methods, Factories & Helpers


    def __repr__(self) -> str:
        """Return string representation of BrowserAdapter."""
        return "BrowserAdapter()"
