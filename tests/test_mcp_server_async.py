"""Extended tests for MCP server tools — async tool functions."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from modules.root_mcp_main_entry import (
    qwen_get_audit_log,
    qwen_process_batch,
    qwen_process_single,
    qwen_send_prompt,
    qwen_setup_session,
)


def _mock_tools(**returns: object) -> MagicMock:
    """Build a mock MCP tool surface."""
    tools = MagicMock()
    for name, value in returns.items():
        getattr(tools, name).return_value = value
    return tools


class TestQwenSendPrompt:
    def test_send_prompt_success(self):
        tools = _mock_tools(send_prompt="AI answer")
        with patch("modules.root_mcp_main_entry._tools", return_value=tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_send_prompt("hello", timeout_sec=120))
            loop.close()
            assert "AI answer" in result

    def test_send_prompt_auth_error(self):
        tools = _mock_tools(send_prompt="ERROR [AUTH_REQUIRED]: login")
        with patch("modules.root_mcp_main_entry._tools", return_value=tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_send_prompt("hello"))
            loop.close()
            assert "AUTH_REQUIRED" in result


class TestQwenProcessSingle:
    def test_process_single_success(self, tmp_path):
        task = tmp_path / "task.md"
        task.write_text("task")
        tools = _mock_tools(process_single="Successfully processed task.md")
        with patch("modules.root_mcp_main_entry._tools", return_value=tools):
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
        tools = _mock_tools(process_batch="Batch processing complete. Successfully processed: 0, Failed: 0")
        with patch("modules.root_mcp_main_entry._tools", return_value=tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_process_batch())
            loop.close()
            assert "Batch processing complete" in result


class TestQwenSetupSession:
    def test_setup_session(self):
        tools = _mock_tools(setup_session="Browser session saved to 'x'")
        with patch("modules.root_mcp_main_entry._tools", return_value=tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_setup_session())
            loop.close()
            assert "Browser session saved" in result


class TestQwenGetAuditLogExtended:
    def test_with_entries(self):
        entries = json.dumps([{"run_id": str(i)} for i in range(5)])
        tools = _mock_tools(get_audit_log=entries)
        with patch("modules.root_mcp_main_entry._tools", return_value=tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_get_audit_log(limit=3))
            loop.close()
            records = json.loads(result)
            assert len(records) == 5

    def test_empty_file(self):
        tools = _mock_tools(get_audit_log="[]")
        with patch("modules.root_mcp_main_entry._tools", return_value=tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_get_audit_log())
            loop.close()
            records = json.loads(result)
            assert len(records) == 0
