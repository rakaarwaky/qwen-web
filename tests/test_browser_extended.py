"""Regression tests for browser module — SessionCheck, reset_page, _assert_on_chat_page, _clean_stale_locks."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import Error as PlaywrightError

from src.browser import (
    CHAT_URL,
    LOGIN_FORM_SELECTORS,
    TEXTAREA_SELECTOR,
    SessionCheck,
    _assert_on_chat_page,
    _clean_stale_locks,
    reset_page,
)
from src.types import AuthRequiredError, LifecycleEmitter


# ─── SessionCheck.is_alive ──────────────────────────────────────────────────


class TestSessionCheckIsAlive:
    def test_alive_when_ready_and_textarea(self):
        page = MagicMock()
        page.evaluate.return_value = "complete"
        page.query_selector.return_value = MagicMock()

        checker = SessionCheck(page)
        assert checker.is_alive() is True

    def test_not_alive_page_not_ready(self):
        page = MagicMock()
        page.evaluate.return_value = "loading"

        checker = SessionCheck(page)
        assert checker.is_alive() is False

    def test_not_alive_textarea_missing(self):
        page = MagicMock()
        page.evaluate.return_value = "complete"
        page.query_selector.return_value = None

        checker = SessionCheck(page)
        assert checker.is_alive() is False

    def test_not_alive_playwright_error(self):
        page = MagicMock()
        page.evaluate.side_effect = PlaywrightError("disconnected")

        checker = SessionCheck(page)
        assert checker.is_alive() is False

    def test_not_alive_unexpected_error(self):
        page = MagicMock()
        page.evaluate.side_effect = RuntimeError("something weird")

        checker = SessionCheck(page)
        assert checker.is_alive() is False


# ─── SessionCheck.check_auth ────────────────────────────────────────────────


class TestSessionCheckAuth:
    def test_auth_passes(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        page.query_selector.return_value = MagicMock()

        checker = SessionCheck(page)
        checker.check_auth()  # no exception

    def test_auth_raises_on_login_url(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/login?next=/"

        checker = SessionCheck(page)
        with pytest.raises(AuthRequiredError, match="Not authenticated"):
            checker.check_auth()

    def test_auth_raises_on_passport_url(self):
        page = MagicMock()
        page.url = "https://passport.qwen.ai/auth"

        checker = SessionCheck(page)
        with pytest.raises(AuthRequiredError, match="Not authenticated"):
            checker.check_auth()

    def test_auth_raises_on_browser_error(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        page.query_selector.side_effect = PlaywrightError("crashed")

        checker = SessionCheck(page)
        with pytest.raises(AuthRequiredError, match="Session invalid"):
            checker.check_auth()


# ─── _assert_on_chat_page ──────────────────────────────────────────────────


class TestAssertOnChatPage:
    def test_passes_on_chat_page(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        page.query_selector.return_value = MagicMock()
        _assert_on_chat_page(page)  # no exception

    def test_raises_on_login_url(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/auth/signin"
        with pytest.raises(AuthRequiredError, match="Not authenticated"):
            _assert_on_chat_page(page)

    def test_raises_on_sso_url(self):
        page = MagicMock()
        page.url = "https://sso.example.com/sso"
        with pytest.raises(AuthRequiredError, match="Not authenticated"):
            _assert_on_chat_page(page)

    def test_raises_when_login_form_detected(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        page.query_selector.return_value = None  # no textarea

        login_form = MagicMock()
        login_form.count.return_value = 1

        def locator_factory(sel):
            if sel in LOGIN_FORM_SELECTORS:
                return login_form
            return MagicMock(count=0)

        page.locator.side_effect = locator_factory
        with pytest.raises(AuthRequiredError, match="login form detected"):
            _assert_on_chat_page(page)

    def test_no_textarea_no_login_form_logs_warning(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        page.query_selector.return_value = None
        mock_loc = MagicMock()
        mock_loc.count.return_value = 0
        page.locator.return_value = mock_loc
        # Should not raise — just logs a warning
        _assert_on_chat_page(page)


# ─── reset_page ────────────────────────────────────────────────────────────


class TestResetPage:
    def test_resets_to_chat_url(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        reset_page(page, emitter)

        page.goto.assert_called_once_with(CHAT_URL, wait_until="domcontentloaded", timeout=10_000)
        emitter.emit.assert_called_once()

    def test_handles_playwright_error_gracefully(self):
        page = MagicMock()
        page.goto.side_effect = PlaywrightError("navigation failed")
        emitter = MagicMock(spec=LifecycleEmitter)

        reset_page(page, emitter)  # should not raise


# ─── _clean_stale_locks ────────────────────────────────────────────────────


class TestCleanStaleLocks:
    def test_removes_existing_locks(self, tmp_path):
        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            (tmp_path / name).write_text("lock")

        _clean_stale_locks(str(tmp_path))

        for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
            assert not (tmp_path / name).exists()

    def test_removes_symlink_locks(self, tmp_path):
        lock = tmp_path / "SingletonLock"
        lock.symlink_to("/nonexistent")

        _clean_stale_locks(str(tmp_path))
        assert not lock.exists()

    def test_no_error_on_missing_dir(self):
        _clean_stale_locks("/nonexistent/path/that/does/not/exist")

    def test_no_error_on_empty_dir(self, tmp_path):
        _clean_stale_locks(str(tmp_path))  # no locks to clean
