"""Unit tests for browser session management and lifecycle helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.core.src.capabilities_browser_adapter import BrowserAdapter, SessionCheck
from modules.shared.src import AuthRequiredError, LifecycleEmitter
from modules.shared.src.taxonomy_core_event import (
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_WEB_LOADED,
)


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
    # Simulate the model switch succeeding: the picker now reports Qwen3.8-Max.
    mock_page.get_by_role.return_value.inner_text.return_value = "Select Model Qwen3.8-Max"
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    BrowserAdapter().navigate_to_chat(mock_page, mock_emitter)

    # navigate_to_chat emits WEB_LOADED, LOGIN_VERIFIED, then MODEL_VERIFIED.
    emitted_events = [call.args[0] for call in mock_emitter.emit.call_args_list]
    assert emitted_events == [EVENT_WEB_LOADED, EVENT_LOGIN_VERIFIED, EVENT_MODEL_VERIFIED]


def test_clean_stale_locks(tmp_path: Path):
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    lock_file = session_dir / "SingletonLock"
    lock_file.write_text("lock")

    BrowserAdapter()._clean_stale_locks(str(session_dir))
    assert not lock_file.exists()


def test_ensure_default_model_clicks_default_option():
    from modules.shared.src.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    picker = MagicMock()
    option = MagicMock()
    locators = {MODEL_SELECTOR_BUTTON_NAME: picker, DEFAULT_MODEL: option}

    def _fake_get_by_role(role, name=None):
        return locators.get(name or "", MagicMock())

    mock_page.get_by_role.side_effect = _fake_get_by_role

    BrowserAdapter().ensure_default_model(mock_page)

    picker.wait_for.assert_called_once()
    picker.click.assert_called_once()
    option.wait_for.assert_called_once()
    option.click.assert_called_once()
    mock_page.wait_for_timeout.assert_called_once()


def test_ensure_default_model_swallows_error():
    from playwright.sync_api import Error as PwError

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.wait_for.side_effect = PwError("picker missing")

    # Best-effort: must never raise, so the prompt pipeline is not blocked.
    BrowserAdapter().ensure_default_model(mock_page)


def test_verify_default_model_ok():
    from modules.shared.src.taxonomy_core_constant import DEFAULT_MODEL

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.inner_text.return_value = f"Select Model {DEFAULT_MODEL}"

    # Must not raise when the picker reports the hardcoded default.
    BrowserAdapter()._verify_default_model(mock_page)


def test_verify_default_model_raises_on_mismatch():
    from modules.shared.src.taxonomy_core_error import ModelSwitchError

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.inner_text.return_value = "Select Model Qwen3.7-Plus"

    with pytest.raises(ModelSwitchError, match="Default model not active"):
        BrowserAdapter()._verify_default_model(mock_page)


def test_verify_default_model_raises_when_unreadable():
    from playwright.sync_api import Error as PwError

    from modules.shared.src.taxonomy_core_error import ModelSwitchError

    mock_page = MagicMock()
    mock_page.get_by_role.return_value.wait_for.side_effect = PwError("picker gone")

    with pytest.raises(ModelSwitchError, match="Cannot read active model"):
        BrowserAdapter()._verify_default_model(mock_page)


MODEL_SELECTOR_BUTTON_NAME = "Select Model"
