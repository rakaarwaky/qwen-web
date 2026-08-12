"""Tests for agent_core_orchestrator — send_file pipeline error paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.core.src.agent_core_orchestrator import CoreOrchestrator
from modules.shared.src import QwenCliError


def _make_orchestrator(**overrides: object) -> CoreOrchestrator:
    """Build an orchestrator with mock capabilities."""
    defaults = {
        "browser": MagicMock(),
        "injector": MagicMock(),
        "sender": MagicMock(),
        "streamer": MagicMock(),
        "uploader": MagicMock(),
        "saver": MagicMock(),
        "audit": MagicMock(),
        "observability": MagicMock(),
    }
    defaults.update(overrides)
    return CoreOrchestrator(**defaults)  # type: ignore[arg-type]


class TestSendFile:
    def test_send_file_os_error(self, tmp_path):
        orch = _make_orchestrator()
        page = MagicMock()
        with pytest.raises(QwenCliError, match="Failed to read"):
            orch.send_file(page, tmp_path / "nonexistent.md", timeout_sec=10)

    def test_send_file_timeout_error(self, tmp_path):
        orch = _make_orchestrator()
        page = MagicMock()
        orch._sender.count_messages.return_value = 0
        orch._uploader.upload_attachment.return_value = True
        orch._streamer.wait_for_response.return_value = None

        f = tmp_path / "task.md"
        f.write_text("hello")

        with pytest.raises(TimeoutError, match="Timeout"):
            orch.send_file(page, f, timeout_sec=10)

    def test_type_slowly_delegates(self):
        orch = _make_orchestrator()
        page = MagicMock()
        textarea = MagicMock()
        orch._type_slowly(page, textarea, "text", delay_ms=10)
        textarea.type.assert_called_once_with("text", delay=10)

    def test_count_messages_delegates(self):
        orch = _make_orchestrator()
        page = MagicMock()
        orch._sender.count_messages.return_value = 2
        result = orch._count_messages(page)
        assert result == 2

    def test_wait_for_response_delegates(self):
        orch = _make_orchestrator()
        page = MagicMock()
        orch._streamer.wait_for_response.return_value = "response"
        result = orch._wait_for_response(page, 10, 0)
        assert result == "response"
