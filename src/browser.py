"""Browser lifecycle management for Playwright persistent context."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator

from playwright.sync_api import BrowserContext, sync_playwright
from tenacity import RetryCallState, Retrying, stop_after_attempt, wait_fixed

try:
    from .config import AppConfig
    from .observability import get_logger, start_span
except ImportError:
    from config import AppConfig
    from observability import get_logger, start_span

log = get_logger("browser")


def _launch_context(p: Any, kwargs: Dict[str, Any]) -> BrowserContext:
    """Launches the persistent context with tenacity retry for transient crashes."""

    def _before_sleep(retry_state: RetryCallState) -> None:
        log.warning(
            "browser_launch_failed_retrying",
            attempt=retry_state.attempt_number,
            next_wait_sec=retry_state.next_action.sleep,
            error=str(retry_state.outcome.exception()),
        )

    for attempt in Retrying(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        before_sleep=_before_sleep,
        reraise=True,
    ):
        with attempt:
            return p.chromium.launch_persistent_context(**kwargs)
    raise RuntimeError("browser launch failed after retries")  # pragma: no cover


@contextmanager
def browser_session(cfg: AppConfig) -> Iterator[BrowserContext]:
    """Manages persistent Chromium browser context with session caching and asset optimization."""
    cfg.session_path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(cfg.session_path, 0o700)
    except Exception as e:
        log.debug("failed_setting_session_permissions", error=str(e))
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

    with start_span("browser_session") as span:
        if span is not None:
            span.set_attribute("headless", cfg.headless)
            span.set_attribute("mode", cfg.mode)
            span.set_attribute("session_path", str(cfg.session_path))
        with sync_playwright() as p:
            ctx = _launch_context(p, kwargs)
            if cfg.mode != "login":
                # Abort heavy static assets directly by pattern to prevent IPC overhead on XHR/SSE requests
                ctx.route("**/*.{png,jpg,jpeg,gif,webp,mp4,mp3,woff,woff2,ttf,otf}", lambda r: r.abort())
            try:
                yield ctx
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
