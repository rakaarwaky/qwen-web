"""Unit tests for browser session management and lifecycle helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.core.src.capabilities_browser_adapter import BrowserAdapter, SessionCheck
from modules.shared.src import AuthRequiredError, LifecycleEmitter
from modules.shared.src.taxonomy_core_event import EVENT_LOGIN_VERIFIED, EVENT_WEB_LOADED


def test_session_check_is_alive_success():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "complete"
    mock_page.query_selector.return_value = MagicMock()

    checker = SessionCheck(mock_page)
    assert checker.is_alive() is True


def test_session_check_not_ready():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "loading"

    checker = SessionCheck(mock_page)
    assert checker.is_alive() is False


def test_session_check_textarea_missing():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "complete"
    mock_page.query_selector.return_value = None

    checker = SessionCheck(mock_page)
    assert checker.is_alive() is False


def test_session_check_auth_redirect():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/login"

    checker = SessionCheck(mock_page)
    with pytest.raises(AuthRequiredError, match="Not authenticated"):
        checker.check_auth()


def test_check_auth_valid():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    loc = MagicMock()
    loc.count.return_value = 0
    mock_page.locator.return_value = loc
    mock_page.query_selector.return_value = MagicMock()
    BrowserAdapter().check_auth(mock_page)


def test_check_auth_login_url():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/passport/login"
    loc = MagicMock()
    loc.count.return_value = 0
    mock_page.locator.return_value = loc

    with pytest.raises(AuthRequiredError, match="Not authenticated"):
        BrowserAdapter().check_auth(mock_page)


def test_reset_page_emits_reconnecting():
    mock_page = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    BrowserAdapter().reset_page(mock_page, mock_emitter)
    mock_emitter.emit.assert_called_once()
    mock_page.goto.assert_called_once()


def test_navigate_to_chat_emits_web_loaded():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    loc = MagicMock()
    loc.count.return_value = 0
    loc.first.is_visible.return_value = False
    loc.first.is_enabled.return_value = False
    mock_page.locator.return_value = loc
    mock_page.query_selector.return_value = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    BrowserAdapter().navigate_to_chat(mock_page, mock_emitter)

    # navigate_to_chat emits EVENT_LOGIN_VERIFIED then EVENT_WEB_LOADED, in order.
    emitted_events = [call.args[0] for call in mock_emitter.emit.call_args_list]
    assert emitted_events == [EVENT_LOGIN_VERIFIED, EVENT_WEB_LOADED]


def test_clean_stale_locks(tmp_path: Path):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    lock_file = session_dir / "SingletonLock"
    lock_file.write_text("lock")

    BrowserAdapter()._clean_stale_locks(str(session_dir))
    assert not lock_file.exists()
