"""Extended tests for mcp_server.py — async tool functions."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.root_mcp_main_entry import (
    qwen_get_audit_log,
    qwen_send_prompt,
    qwen_process_single,
    qwen_process_batch,
    qwen_setup_session,
)


class TestQwenSendPrompt:
    def test_send_prompt_success(self):
        with patch("modules.root_mcp_main_entry.browser_session") as mock_bs, \
             patch("modules.root_mcp_main_entry.QwenClient") as mock_client:
            mock_ctx = MagicMock()
            mock_bs.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.send_file.return_value = "AI answer"

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_send_prompt("hello", timeout_sec=120))
            loop.close()
            assert "AI answer" in result

    def test_send_prompt_auth_error(self):
        from modules.shared.src import AuthRequiredError
        with patch("modules.root_mcp_main_entry.browser_session") as mock_bs, \
             patch("modules.root_mcp_main_entry.QwenClient") as mock_client:
            mock_ctx = MagicMock()
            mock_bs.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.send_file.side_effect = AuthRequiredError("login")

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_send_prompt("hello"))
            loop.close()
            assert "AUTH_REQUIRED" in result


class TestQwenProcessSingle:
    def test_process_single_success(self, tmp_path):
        task = tmp_path / "task.md"
        task.write_text("task")

        with patch("modules.root_mcp_main_entry.browser_session") as mock_bs, \
             patch("modules.root_mcp_main_entry.QwenClient") as mock_client, \
             patch("modules.root_mcp_main_entry._process_file"), \
             patch("modules.root_mcp_main_entry.AuditLog"):
            mock_ctx = MagicMock()
            mock_bs.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_process_single(str(task)))
            loop.close()
            assert "Successfully processed" in result

    def test_process_single_file_not_found(self):
        loop = asyncio.new_event_loop()
        with pytest.raises(FileNotFoundError):
            loop.run_until_complete(qwen_process_single("/nonexistent/file.md"))
        loop.close()


class TestQwenProcessBatch:
    def test_process_batch_empty(self):
        with patch("modules.root_mcp_main_entry.browser_session") as mock_bs, \
             patch("modules.root_mcp_main_entry.QwenClient"), \
             patch("modules.root_mcp_main_entry._iter_todo", return_value=iter([])), \
             patch("modules.root_mcp_main_entry.AuditLog"):
            mock_ctx = MagicMock()
            mock_bs.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_process_batch())
            loop.close()
            assert "Batch processing complete" in result


class TestQwenSetupSession:
    def test_setup_session(self):
        with patch("modules.root_mcp_main_entry.browser_session") as mock_bs:
            mock_ctx = MagicMock()
            mock_page = MagicMock()
            mock_ctx.pages = [mock_page]
            mock_bs.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_setup_session())
            loop.close()
            assert "Browser session saved" in result


class TestQwenGetAuditLogExtended:
    def test_with_entries(self, tmp_path):
        log_file = tmp_path / "audit_history.jsonl"
        entries = [json.dumps({"run_id": str(i)}) for i in range(5)]
        log_file.write_text("\n".join(entries) + "\n")
        with patch("modules.root_mcp_main_entry.DEFAULT_LOG", tmp_path):
            result = qwen_get_audit_log(limit=3)
            records = json.loads(result)
            assert len(records) == 3

    def test_empty_file(self, tmp_path):
        log_file = tmp_path / "audit_history.jsonl"
        log_file.write_text("")
        with patch("modules.root_mcp_main_entry.DEFAULT_LOG", tmp_path):
            result = qwen_get_audit_log()
            records = json.loads(result)
            assert len(records) == 0
