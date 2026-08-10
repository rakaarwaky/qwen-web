"""Browser lifecycle management for Playwright persistent context."""
from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

from playwright.sync_api import BrowserContext, Page, sync_playwright
from tenacity import RetryCallState, Retrying, stop_after_attempt, wait_fixed

from .types import AppConfig, AuthRequiredError, BrowserLaunchError, LifecycleEmitter, EVENT_NETWORK_RECONNECTING, EVENT_WEB_LOADED
from .observability import get_logger, start_span

log = get_logger("browser")


# ─── Session stability check ─────────────────────────────────────────────────
class SessionCheck:
    """Validates that the browser session and Qwen chat UI are alive."""

    def __init__(self, page: Page) -> None:
        self.page = page

    def is_alive(self) -> bool:
        """Return True if the session is stable and the chat UI is responsive."""
        try:
            self.page.evaluate("() => document.readyState")
            ready = self.page.evaluate("() => document.readyState")
            if ready != "complete":
                log.warning("session_check_failed", reason="page_not_ready", ready=ready)
                return False

            el = self.page.query_selector("textarea.message-input-textarea")
            if not el:
                log.warning("session_check_failed", reason="textarea_missing")
                return False

            return True
        except Exception as exc:
            log.warning("session_check_failed", reason=str(exc))
            return False

    def check_auth(self) -> None:
        """Raise AuthRequiredError if the session is no longer authenticated."""
        try:
            current_url = self.page.url.lower()
            if any(k in current_url for k in ("login", "passport", "auth", "signin")):
                raise AuthRequiredError("Session expired — redirected to login page.")

            self.page.query_selector("textarea.message-input-textarea")
        except AuthRequiredError:
            raise
        except Exception as exc:
            raise AuthRequiredError(f"Session invalid: {exc}")


def reset_page(page: Page, emitter: LifecycleEmitter) -> None:
    """Reset the page to a clean state by navigating back to chat.qwen.ai."""
    try:
        emitter.emit(EVENT_NETWORK_RECONNECTING, {"url": "https://chat.qwen.ai/"})
        page.goto("https://chat.qwen.ai/", wait_until="domcontentloaded", timeout=10_000)
        page.wait_for_load_state("domcontentloaded", timeout=15_000)
    except Exception as e:
        log.warning("Error resetting page: %s", e)


def navigate_to_chat(page: Page, emitter: LifecycleEmitter) -> None:
    """Navigate to chat.qwen.ai and emit WEB_LOADED."""
    page.goto("https://chat.qwen.ai/", wait_until="domcontentloaded", timeout=30_000)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15_000)
    except Exception:
        pass
    emitter.emit(EVENT_WEB_LOADED, {"url": page.url})


def check_auth(page: Page) -> None:
    """Raise AuthRequiredError if the page is on a login/auth URL."""
    current_url = page.url.lower()
    if any(k in current_url for k in ("login", "passport", "auth", "signin")):
        raise AuthRequiredError("No active login session. Run 'qwc --login' to authenticate.")


def _clean_stale_locks(user_data_dir: str) -> None:
    """Clean up stale Chromium lock files if process crashed or before launch."""
    session_path = Path(user_data_dir)
    for fname in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        lock_path = session_path / fname
        try:
            if lock_path.is_symlink() or lock_path.exists():
                lock_path.unlink(missing_ok=True)
        except Exception:
            pass


def _launch_context(p: Any, kwargs: Dict[str, Any]) -> Any:
    """Launches the persistent context with tenacity retry for transient crashes."""
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
def browser_session(cfg: AppConfig) -> Iterator[BrowserContext]:
    """Manages persistent Chromium browser context with session caching and asset optimization.

    Linux-native defaults:
      - Uses /usr/bin/google-chrome (or chromium-browser fallback).
      - --disable-gpu on headless to avoid GPU-related crashes.
      - --no-sandbox enabled for container/headless environments.
      - Blocks heavy static assets to reduce IPC overhead.
    """
    cfg.session_path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(cfg.session_path, 0o700)
    except Exception as e:
        log.debug("failed_setting_session_permissions", error=str(e))

    # Chrome binary path (Linux-native, dynamic discovery)
    chrome_bin = (
        shutil.which("google-chrome")
        or shutil.which("google-chrome-stable")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or ""
    )

    # Linux-specific Chrome args (P5)
    chrome_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
    ]

    # Headless GPU disable (Linux-native, P5)
    if cfg.headless:
        chrome_args.extend([
            "--disable-gpu",
            "--disable-software-compositing",
        ])

    kwargs = {
        "user_data_dir": str(cfg.session_path),
        "headless": cfg.headless,
        "permissions": ["clipboard-read", "clipboard-write"],
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "args": chrome_args,
        "viewport": {"width": 1280, "height": 800},
    }

    if chrome_bin and Path(chrome_bin).exists():
        kwargs["executable_path"] = chrome_bin

    with start_span("browser_session") as span:
        if span is not None:
            span.set_attribute("headless", cfg.headless)
            span.set_attribute("mode", cfg.mode)
            span.set_attribute("session_path", str(cfg.session_path))
        try:
            import asyncio
            if hasattr(asyncio, "_set_running_loop"):
                asyncio._set_running_loop(None)
        except Exception:
            pass

        try:
            with sync_playwright() as p:
                ctx = _launch_context(p, kwargs)
                if cfg.mode != "login":
                    # Abort heavy static assets directly by pattern to prevent IPC overhead on XHR/SSE requests
                    ctx.route(
                        "**/*.{png,jpg,jpeg,gif,webp,mp4,mp3,woff,woff2,ttf,otf}",
                        lambda r: r.abort(),
                    )
                try:
                    yield ctx
                finally:
                    try:
                        ctx.close()
                    except Exception:
                        pass
        except AuthRequiredError:
            raise
        except Exception as e:
            log.critical("browser_launch_failed", error=str(e))
            raise BrowserLaunchError(f"Failed to launch browser: {e}")
