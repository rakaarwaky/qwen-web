"""Capabilities: Playwright browser adapter (AES403).

Implements IBrowserProtocol, IInjectionProtocol, ISendProtocol,
IStreamProtocol, and IUploadProtocol.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from playwright.sync_api import (
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
)
from tenacity import RetryCallState, Retrying, stop_after_attempt, wait_fixed

from ..common.taxonomy_core_event import EVENT_DOCUMENT_PARSED, EVENT_NETWORK_RECONNECTING, EVENT_WEB_LOADED
from ..common.taxonomy_core_vo import (
    ChromeProfile,
    ConfigPath,
    DisableSandboxFlag,
    HeadlessFlag,
    InputPath,
    ServerName,
    UserAgent,
)
from ..common.taxonomy_core_constant import (
    TEXTAREA_SELECTOR,
    CHAT_URL,
    AUTH_KEYWORDS,
    LOGIN_FORM_SELECTORS,
    MAX_ATTEMPTS,
)
from ..common.taxonomy_domain_error import AuthRequiredError, BrowserLaunchError
from ..core.contract_core_protocol import IBrowserProtocol, IInjectionProtocol, ISendProtocol, IStreamProtocol, IUploadProtocol
from .utility_core_path import resolve_role_paths

log = __import__("logging").getLogger("capabilities_browser_adapter")


class SessionCheck:
    """Validates that the browser session and Qwen chat UI are alive."""

    def __init__(self, page: Page) -> None:
        self.page = page

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
        except PlaywrightError as exc:
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
        except PlaywrightError as exc:
            raise AuthRequiredError(f"Session invalid (browser error): {exc}")


class BrowserAdapter(IBrowserProtocol):
    """Playwright-based browser session manager."""

    def __init__(
        self,
        headless: HeadlessFlag = HeadlessFlag(False),
        session_path: ConfigPath = ConfigPath(str(Path.home() / ".local" / "share" / "qwen-web" / "qwen_session")),
        chrome_profile: ChromeProfile = ChromeProfile("qwen-web-profile"),
        disable_sandbox: DisableSandboxFlag = DisableSandboxFlag(True),
        user_agent: str | None = None,
        viewport: tuple[int, int] | None = None,
    ) -> None:
        self.headless = headless
        self.session_path = Path(session_path)
        self.chrome_profile = chrome_profile
        self.disable_sandbox = disable_sandbox
        self.user_agent = user_agent
        self.viewport = {"width": viewport[0], "height": viewport[1]} if viewport else {"width": 1280, "height": 800}
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def browser_session(self) -> Iterator[BrowserContext]:
        """Context manager for browser lifecycle."""
        self.session_path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.session_path, 0o700)
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

        if self.headless:
            chrome_args.extend([
                "--disable-gpu",
                "--disable-software-compositing",
            ])

        kwargs: dict[str, Any] = {
            "user_data_dir": str(self.session_path),
            "headless": self.headless,
            "permissions": ["clipboard-read", "clipboard-write"],
            "user_agent": self.user_agent or UserAgent(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "args": chrome_args,
            "viewport": self.viewport,
        }

        if chrome_bin and Path(chrome_bin).exists():
            kwargs["executable_path"] = chrome_bin

        try:
            with sync_playwright() as p:
                ctx = self._launch_context(p, kwargs)
                if ctx:
                    self._context = ctx
                    yield ctx
                    try:
                        ctx.close()
                    except PlaywrightError as e:
                        log.warning("Error closing browser context: %s", e)
        except AuthRequiredError:
            raise
        except Exception as e:
            log.critical("browser_launch_failed", error=str(e))
            raise BrowserLaunchError(f"Failed to launch browser: {e}") from e

    def _launch_context(self, p: Playwright, kwargs: dict[str, Any]) -> BrowserContext | None:
        """Launch the persistent context with tenacity retry for transient crashes."""
        user_data_dir = kwargs.get("user_data_dir", "")
        if user_data_dir:
            _clean_stale_locks(user_data_dir)

        def _before_sleep(retry_state: RetryCallState) -> None:
            sleep_val = retry_state.next_action.sleep if retry_state.next_action else 2
            if user_data_dir:
                _clean_stale_locks(user_data_dir)
            log.warning(
                "browser_launch_failed_retrying",
                attempt=retry_state.attempt_number,
                next_wait_sec=sleep_val,
                error=str(retry_state.outcome.exception()) if retry_state.outcome else "unknown",
            )

        for attempt in Retrying(
            stop=stop_after_attempt(MAX_ATTEMPTS),
            wait=wait_fixed(2),
            before_sleep=_before_sleep,
            reraise=True,
        ):
            with attempt:
                ctx = p.chromium.launch_persistent_context(**kwargs)
                return ctx

        return None

    def is_alive(self) -> bool:
        if self._page:
            checker = SessionCheck(self._page)
            return checker.is_alive()
        return False

    def check_auth(self) -> None:
        if self._page:
            _assert_on_chat_page(self._page)

    def navigate_to_chat(self) -> None:
        if self._page:
            from ..common.taxonomy_core_event import LifecycleEmitter
            emitter = LifecycleEmitter()
            _navigate_to_chat_internal(self._page, emitter)

    def get_page(self) -> Page | None:
        return self._page or (self._context.pages[0] if self._context and self._context.pages else None)

    def reset_page(self) -> None:
        if self._page:
            from ..common.taxonomy_core_event import LifecycleEmitter
            emitter = LifecycleEmitter()
            reset_page(self._page, emitter)


# Standalone functions
def _clean_stale_locks(user_data_dir: str) -> None:
    """Clean up stale Chromium lock files if process crashed or before launch."""
    session_path = Path(user_data_dir)
    for fname in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        lock_path = session_path / fname
        try:
            if lock_path.is_symlink() or lock_path.exists():
                lock_path.unlink(missing_ok=True)
        except OSError as e:
            log.warning("Failed to delete stale lock %s: %s", lock_path, e)


def reset_page(page: Page, emitter: Any) -> None:
    """Reset the page to a clean state by navigating back to chat.qwen.ai."""
    try:
        emitter.emit(EVENT_NETWORK_RECONNECTING, {"url": CHAT_URL})
        page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=10_000)
        page.wait_for_load_state("domcontentloaded", timeout=15_000)
    except PlaywrightError as e:
        log.warning("Failed to reset page: %s", e)


def _assert_on_chat_page(page: Page) -> None:
    """Raise AuthRequiredError if the page is a login/auth page."""
    current_url = page.url.lower()

    if any(k in current_url for k in AUTH_KEYWORDS):
        raise AuthRequiredError(
            f"Not authenticated — browser is on login page ({page.url}). "
            "Run 'qwen-web-cli --login' to save your session first."
        )

    if not page.query_selector(TEXTAREA_SELECTOR):
        for sel in LOGIN_FORM_SELECTORS:
            try:
                if page.locator(sel).count() > 0:
                    raise AuthRequiredError(
                        f"Not authenticated — login form detected ({sel}). "
                        "Run 'qwen-web-cli --login' to save your session first."
                    )
            except AuthRequiredError:
                raise
            except PlaywrightError:
                continue
        log.warning("chat_textarea_missing_but_no_login_form_detected", url=page.url)


def _navigate_to_chat_internal(page: Page, emitter: Any) -> None:
    """Internal: navigate to chat and emit event."""
    try:
        page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=30_000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15_000)
        except PlaywrightError as e:
            log.warning("Load state wait failed, proceeding: %s", e)
        _assert_on_chat_page(page)
    finally:
        emitter.emit(EVENT_WEB_LOADED, {"url": CHAT_URL})


def navigate_to_chat(page: Page, emitter: Any) -> None:
    """Navigate to chat.qwen.ai, emit WEB_LOADED, and verify authenticated session."""
    _navigate_to_chat_internal(page, emitter)


# Backward-compat exports
SessionCheck = SessionCheck
check_auth = _assert_on_chat_page