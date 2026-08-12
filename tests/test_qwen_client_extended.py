"""Tests for qwen_client.py — remaining uncovered lines."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from playwright.sync_api import ElementHandle

from modules.core.src.agent_core_orchestrator import QwenClient
from modules.shared.src import AppConfig, LifecycleEmitter, QwenCliError


class TestQwenClientSendFile:
    def test_send_file_no_page_raises(self):
        client = QwenClient(None)
        with pytest.raises(RuntimeError, match="Browser not started"):
            client.send_file(Path("/fake.md"), timeout_sec=10)

    def test_send_file_os_error(self, tmp_path):
        ctx = MagicMock()
        ctx.pages = [MagicMock()]
        client = QwenClient(ctx)
        with pytest.raises(QwenCliError, match="Failed to read"):
            client.send_file(tmp_path / "nonexistent.md", timeout_sec=10)

    def test_send_file_timeout_error(self, tmp_path):
        ctx = MagicMock()
        page = MagicMock()
        ctx.pages = [page]
        client = QwenClient(ctx)

        f = tmp_path / "task.md"
        f.write_text("hello")

        with patch("modules.qwen_client.navigate_to_chat"), \
             patch("modules.qwen_client._check_auth"), \
             patch("modules.qwen_client.count_messages", return_value=0), \
             patch("modules.qwen_client.find_input"), \
             patch("modules.qwen_client.upload_attachment", return_value=True), \
             patch("modules.qwen_client.inject_text"), \
             patch("modules.qwen_client.click_send"), \
             patch("modules.qwen_client.wait_for_response", return_value=None):
            with pytest.raises(TimeoutError, match="Timeout"):
                client.send_file(f, timeout_sec=10)

    def test_type_slowly_delegates(self):
        ctx = MagicMock()
        page = MagicMock()
        ctx.pages = [page]
        client = QwenClient(ctx)
        textarea = MagicMock(spec=ElementHandle)
        client._type_slowly(textarea, "text", delay_ms=10)
        textarea.type.assert_called_once_with("text", delay=10)

    def test_count_messages_delegates(self):
        ctx = MagicMock()
        page = MagicMock()
        page.evaluate.return_value = 2
        ctx.pages = [page]
        client = QwenClient(ctx)
        result = client._count_messages()
        assert isinstance(result, int)

    def test_wait_for_response_delegates(self):
        ctx = MagicMock()
        page = MagicMock()
        ctx.pages = [page]
        client = QwenClient(ctx)
        with patch("modules.qwen_client.wait_for_response", return_value="response"):
            result = client._wait_for_response(10, 0)
            assert result == "response"
