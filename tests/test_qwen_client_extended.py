"""Tests for agent_core_orchestrator — send_file pipeline error paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import Error

from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.shared.src import QwenCliError
from tests.helpers import make_test_orchestrator


class TestSendFile:
    def test_send_file_os_error(self, tmp_path):
        orch = make_test_orchestrator()
        page = MagicMock()
        with pytest.raises(QwenCliError, match="Failed to read"):
            orch.send_file(page, tmp_path / "nonexistent.md", timeout_sec=10)

    def test_send_file_timeout_error(self, tmp_path):
        orch = make_test_orchestrator()
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
