"""Regression tests for saved-session validation and manual login lifecycle."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.cli.src.surface_cli_login_command import handle
from modules.core.src.agent_core_orchestrator import CoreOrchestrator
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.shared.src import AppConfig, AuthRequiredError


class _BrowserHarness:
    """Small browser protocol fake that records context lifetime and config."""

    def __init__(self, session_results: list[bool]) -> None:
        self._session_results = iter(session_results)
        self.context_configs: list[object] = []
        self.active = False
        self.page = MagicMock()
        self.page.pages = [self.page]

    @contextmanager
    def browser_session(self, cfg):
        self.context_configs.append(cfg)
        self.active = True
        context = MagicMock()
        context.pages = [self.page]
        try:
            yield context
        finally:
            self.active = False

    def navigate_to_chat(self, page, emitter) -> None:
        return None

    def check_auth(self, page) -> None:
        return None

    def check_session(self, page) -> bool:
        return next(self._session_results)

    def reset_page(self, page, emitter) -> None:
        return None


def _orchestrator(browser: _BrowserHarness) -> CoreOrchestrator:
    """Build an orchestrator with the non-browser capabilities mocked."""
    observability = MagicMock()
    observability.get_logger.return_value = MagicMock()
    return CoreOrchestrator(
        browser=browser,
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        uploader=MagicMock(),
        saver=MagicMock(),
        audit=MagicMock(),
        observability=observability,
        workspace=MagicMock(),
    )


def test_existing_valid_session_skips_visible_login(tmp_path: Path) -> None:
    """A valid profile reports its state without opening a headed context."""
    session_path = tmp_path / "session"
    session_path.mkdir()
    browser = _BrowserHarness([True])
    confirmation = MagicMock()

    result = _orchestrator(browser).setup_session(
        wait_for_confirmation=confirmation,
        session_path=session_path,
    )

    assert "already valid" in result
    confirmation.assert_not_called()
    assert len(browser.context_configs) == 1
    validation_cfg = browser.context_configs[0]
    assert validation_cfg.mode == "session-check"
    assert validation_cfg.headless is True


def test_manual_login_keeps_browser_open_until_confirmation(tmp_path: Path) -> None:
    """The confirmation prompt runs before the browser context is closed."""
    session_path = tmp_path / "session"
    browser = _BrowserHarness([True])
    confirmation = MagicMock(side_effect=lambda: _assert_browser_active(browser))

    result = _orchestrator(browser).setup_session(
        wait_for_confirmation=confirmation,
        session_path=session_path,
    )

    assert "completed successfully" in result
    confirmation.assert_called_once_with()
    assert len(browser.context_configs) == 1
    login_cfg = browser.context_configs[0]
    assert login_cfg.mode == "login"
    assert login_cfg.headless is False
    assert browser.active is False


def test_invalid_saved_session_falls_back_to_manual_login(tmp_path: Path) -> None:
    """An expired profile is checked first, then replaced through manual login."""
    session_path = tmp_path / "session"
    session_path.mkdir()
    browser = _BrowserHarness([False, True])
    confirmation = MagicMock(side_effect=lambda: _assert_browser_active(browser))

    result = _orchestrator(browser).setup_session(
        wait_for_confirmation=confirmation,
        session_path=session_path,
    )

    assert "completed successfully" in result
    assert [cfg.mode for cfg in browser.context_configs] == ["session-check", "login"]
    assert browser.context_configs[1].headless is False


def test_manual_login_reports_invalid_final_state(tmp_path: Path) -> None:
    """Pressing ENTER before authentication produces an actionable error."""
    browser = _BrowserHarness([False])

    with pytest.raises(AuthRequiredError, match="did not produce a valid"):
        _orchestrator(browser).setup_session(
            wait_for_confirmation=lambda: _assert_browser_active(browser),
            session_path=tmp_path / "session",
        )

    assert browser.active is False


def _assert_browser_active(browser: _BrowserHarness) -> None:
    """Assert that a callback was invoked inside the context manager."""
    assert browser.active is True


def test_cli_login_passes_confirmation_callback_to_core(tmp_path: Path) -> None:
    """The CLI owns the ENTER prompt but executes it through the core context."""
    cfg = AppConfig(
        mode="login",
        input_path=tmp_path / "input",
        output_path=tmp_path / "output",
        done_path=tmp_path / "done",
        failed_path=tmp_path / "failed",
        proc_path=tmp_path / "proc",
        session_path=tmp_path / "session",
    )
    core = MagicMock()
    core.setup_session.return_value = "Manual login completed successfully."

    with patch("sys.stdin") as stdin, patch("builtins.input") as input_fn:
        stdin.isatty.return_value = True
        result = handle(None, core, cfg)

    assert result == {"success": True, "message": "Manual login completed successfully."}
    core.setup_session.assert_called_once()
    kwargs = core.setup_session.call_args.kwargs
    assert kwargs["session_path"] == cfg.session_path
    assert callable(kwargs["wait_for_confirmation"])
    input_fn.assert_not_called()


def test_browser_check_session_requires_authenticated_chat_ui() -> None:
    """The browser capability accepts the chat UI and rejects login URLs."""
    page = MagicMock()
    page.url = "https://chat.qwen.ai/"
    page.evaluate.return_value = "complete"
    page.query_selector.return_value = MagicMock()
    assert BrowserAdapter().check_session(page) is True

    page.url = "https://chat.qwen.ai/login"
    assert BrowserAdapter().check_session(page) is False


def test_manual_login_delays_check_session_after_confirmation(tmp_path: Path) -> None:
    """After wait_for_confirmation, setup_session waits before checking session.

    This prevents the browser from being checked while the page is still
    stabilizing after a manual login — which previously caused a hang.
    """
    import time

    session_path = tmp_path / "session"
    browser = _BrowserHarness([True])
    wait_calls: list[int] = []

    def _patch_page(page):
        original_wait = page.wait_for_timeout
        def recording_wait(ms=0):
            wait_calls.append(ms)
            # Actually sleep for the delay so timing test works
            time.sleep(ms / 1000)
        page.wait_for_timeout = recording_wait

    _patch_page(browser.page)

    confirmation = MagicMock()
    start = time.monotonic()

    result = _orchestrator(browser).setup_session(
        wait_for_confirmation=confirmation,
        session_path=session_path,
    )

    assert "completed successfully" in result
    # The wait_for_timeout should have been called with ~2000ms
    assert len(wait_calls) == 1
    assert wait_calls[0] == 2000
