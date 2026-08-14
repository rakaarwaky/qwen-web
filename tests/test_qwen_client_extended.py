"""Tests for agent_core_orchestrator — send_file pipeline error paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import Error

from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.shared.src import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_DOCUMENT_PARSED,
    EVENT_WEB_LOADED,
    QwenCliError,
)
from tests.helpers import make_test_orchestrator


def _configure_lifecycle_mocks(orch) -> None:
    def navigate(_page, emitter):
        emitter.emit(EVENT_WEB_LOADED, {"url": "test"})

    def upload(_page, _filepath, emitter=None, **_kwargs):
        assert emitter is not None
        emitter.emit(EVENT_DOCUMENT_PARSED, {"file": "test"})
        return True

    def send(_page, emitter, **_kwargs):
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, {"file": "test"})

    orch._browser.navigate_to_chat.side_effect = navigate
    orch._uploader.upload_attachment.side_effect = upload
    orch._sender.click_send.side_effect = send


class TestSendFile:
    def test_send_file_os_error(self, tmp_path):
        orch = make_test_orchestrator()
        page = MagicMock()
        with pytest.raises(QwenCliError, match="Failed to read"):
            orch.send_file(page, tmp_path / "nonexistent.md", timeout_sec=10)

    def test_send_file_timeout_error(self, tmp_path):
        orch = make_test_orchestrator()
        _configure_lifecycle_mocks(orch)
        page = MagicMock()
        orch._sender.count_messages.return_value = 0
        orch._uploader.upload_attachment.return_value = True
        orch._streamer.wait_for_response.return_value = None

        f = tmp_path / "task.md"
        f.write_text("hello")

        with pytest.raises(TimeoutError, match="Timeout"):
            orch.send_file(page, f, timeout_sec=10)

    def test_send_file_delegates_to_capabilities(self, tmp_path):
        orch = make_test_orchestrator()
        _configure_lifecycle_mocks(orch)
        page = MagicMock()
        orch._sender.count_messages.return_value = 2
        orch._uploader.upload_attachment.return_value = True
        orch._streamer.wait_for_response.return_value = "the response"

        f = tmp_path / "task.md"
        f.write_text("hello")

        result = orch.send_file(page, f, timeout_sec=10)

        assert result == "the response"
        orch._streamer.wait_for_response.assert_called_once()
        assert orch._streamer.wait_for_response.call_args[0][2] == 2

    def test_inject_text_types_with_delay_fallback(self):
        """Slow typing is delegated to inject_text's type() fallback."""
        page = MagicMock()
        page.evaluate.return_value = False
        el = MagicMock()
        el.fill.side_effect = Error("fill failed")
        injector = PromptInjector()
        with (
            patch.object(PromptInjector, "find_input", return_value=el),
            patch.object(PromptInjector, "_verify_injection", return_value=True),
        ):
            injector.inject_text(page, "text")
        el.type.assert_called_once_with("text", delay=10)
