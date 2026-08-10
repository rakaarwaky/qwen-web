"""Tests for browser.py — navigate_to_chat, check_auth, _launch_context, browser_session."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.browser import (
    CHAT_URL,
    _launch_context,
    _assert_on_chat_page,
    check_auth,
    navigate_to_chat,
)
from src.types import AppConfig, AuthRequiredError, LifecycleEmitter


class TestNavigateToChat:
    def test_navigates_and_emits(self):
        page = MagicMock()
        page.url = CHAT_URL
        page.query_selector.return_value = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        navigate_to_chat(page, emitter)

        page.goto.assert_called_once()
        emitter.emit.assert_called_once()

    def test_raises_auth_error_on_login_page(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/login"
        emitter = MagicMock(spec=LifecycleEmitter)

        with pytest.raises(AuthRequiredError):
            navigate_to_chat(page, emitter)

    def test_handles_load_state_error(self):
        page = MagicMock()
        page.url = CHAT_URL
        page.query_selector.return_value = MagicMock()
        from playwright.sync_api import Error as PlaywrightError
        page.wait_for_load_state.side_effect = PlaywrightError("timeout")
        emitter = MagicMock(spec=LifecycleEmitter)

        navigate_to_chat(page, emitter)


class TestCheckAuth:
    def test_passes_on_chat_page(self):
        page = MagicMock()
        page.url = CHAT_URL
        page.query_selector.return_value = MagicMock()
        check_auth(page)

    def test_raises_on_login(self):
        page = MagicMock()
        page.url = "https://passport.qwen.ai/auth"
        with pytest.raises(AuthRequiredError):
            check_auth(page)


class TestLaunchContext:
    def test_launches_with_lock_cleanup(self):
        p = MagicMock()
        kwargs = {"user_data_dir": "", "headless": True}

        mock_ctx = MagicMock()
        p.chromium.launch_persistent_context.return_value = mock_ctx

        ctx = _launch_context(p, kwargs)
        assert ctx == mock_ctx

    def test_cleans_locks_before_launch(self, tmp_path):
        p = MagicMock()
        lock_dir = tmp_path / "session"
        lock_dir.mkdir()
        (lock_dir / "SingletonLock").write_text("lock")

        kwargs = {"user_data_dir": str(lock_dir), "headless": True}
        mock_ctx = MagicMock()
        p.chromium.launch_persistent_context.return_value = mock_ctx

        ctx = _launch_context(p, kwargs)
        assert not (lock_dir / "SingletonLock").exists()


class TestAssertOnChatPageExtended:
    def test_passes_with_url_check(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        page.query_selector.return_value = MagicMock()
        _assert_on_chat_page(page)

    def test_raises_on_account_url(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/account/settings"
        with pytest.raises(AuthRequiredError, match="Not authenticated"):
            _assert_on_chat_page(page)
