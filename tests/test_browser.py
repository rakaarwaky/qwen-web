"""Unit tests for browser session management and lifecycle helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.core.src.capabilities_browser_adapter import (
    SessionCheck,
    _clean_stale_locks,
    check_auth,
    navigate_to_chat,
    reset_page,
)
from modules.shared.src import AuthRequiredError, LifecycleEmitter


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
    check_auth(mock_page)


def test_check_auth_login_url():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/passport/login"

    with pytest.raises(AuthRequiredError, match="Not authenticated"):
        check_auth(mock_page)


def test_reset_page_emits_reconnecting():
    mock_page = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    reset_page(mock_page, mock_emitter)
    mock_emitter.emit.assert_called_once()
    mock_page.goto.assert_called_once()


def test_navigate_to_chat_emits_web_loaded():
    mock_page = MagicMock()
    mock_page.url = "https://chat.qwen.ai/"
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    navigate_to_chat(mock_page, mock_emitter)
    mock_emitter.emit.assert_called_once()


def test_clean_stale_locks(tmp_path: Path):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    lock_file = session_dir / "SingletonLock"
    lock_file.write_text("lock")

    _clean_stale_locks(str(session_dir))
    assert not lock_file.exists()
