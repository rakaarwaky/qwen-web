"""Tests for qwen_client.py — remaining uncovered lines."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from playwright.sync_api import ElementHandle

from src.qwen_client import QwenClient
from src.types import (
    EVENT_DOCUMENT_PARSED,
    EVENT_PROMPT_INJECTED,
    EVENT_SEND_CLICKED,
    AppConfig,
    LifecycleEmitter,
    QwenCliError,
)


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

        def mock_upload_attachment(p, f, emitter=None, web_loaded=True):
            if emitter:
                emitter.emit(EVENT_DOCUMENT_PARSED, {"file": str(f), "char_count": 5})
            return True

        def mock_inject_text(p, text, emitter=None):
            if emitter:
                emitter.emit(EVENT_PROMPT_INJECTED, {"text_length": len(text)})

        def mock_click_send(p, emitter, document_parsed=True, prompt_injected=True):
            if emitter:
                emitter.emit(EVENT_SEND_CLICKED, {"selector": "mock"})

        with patch("src.qwen_client.navigate_to_chat"), \
             patch("src.qwen_client._check_auth"), \
             patch("src.qwen_client.count_messages", return_value=0), \
             patch("src.qwen_client.find_input"), \
             patch("src.qwen_client.upload_attachment", side_effect=mock_upload_attachment), \
             patch("src.qwen_client.inject_text", side_effect=mock_inject_text), \
             patch("src.qwen_client.click_send", side_effect=mock_click_send), \
             patch("src.qwen_client.wait_for_response", return_value=None):
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
        with patch("src.qwen_client.wait_for_response", return_value="response"):
            result = client._wait_for_response(10, 0)
            assert result == "response"
