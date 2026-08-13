"""Tests for mcp_server.py — MCP tool functions and helpers."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from modules.root_mcp_main_entry import (
    _get_mcp_app,
    _register_tool,
    qwen_get_audit_log,
)


class TestGetMcpApp:
    def test_returns_app_when_available(self):
        with patch("modules.root_mcp_main_entry.mcp", new_callable=lambda: MagicMock):
            app = _get_mcp_app()
            assert app is not None

    def test_raises_when_mcp_none(self):
        with patch("modules.root_mcp_main_entry.mcp", None), pytest.raises(ImportError, match="mcp"):
            _get_mcp_app()


class TestRegisterTool:
    def test_registers_with_mcp(self):
        mock_mcp = MagicMock()
        mock_mcp.tool.return_value = lambda fn: fn
        with patch("modules.root_mcp_main_entry.mcp", mock_mcp):
            @_register_tool
            async def my_func():
                return "ok"
            result = asyncio.run(my_func())
            assert result == "ok"

    def test_returns_fn_when_mcp_none(self):
        with patch("modules.root_mcp_main_entry.mcp", None):
            @_register_tool
            async def my_func():
                return "ok"
            result = asyncio.run(my_func())
            assert result == "ok"


class TestGetAuditLog:
    def test_no_log_file(self, tmp_path):
        mock_tools = MagicMock()
        mock_tools.get_audit_log.return_value = "Audit log file does not exist yet."
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            result = qwen_get_audit_log()
            assert "does not exist" in result

    def test_with_log_entries(self, tmp_path):
        entries = [
            json.dumps({"run_id": "1", "status": "SUCCESS"}),
            json.dumps({"run_id": "2", "status": "FAILED"}),
        ]
        mock_tools = MagicMock()
        mock_tools.get_audit_log.return_value = "[" + ",".join(entries) + "]"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            result = qwen_get_audit_log(limit=1)
            records = json.loads(result)
            assert len(records) == 2

    def test_empty_log_file(self, tmp_path):
        mock_tools = MagicMock()
        mock_tools.get_audit_log.return_value = "[]"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            result = qwen_get_audit_log()
            records = json.loads(result)
            assert len(records) == 0


class TestRunMcpServer:
    def test_run_mcp_server(self):
        with patch("modules.root_mcp_main_entry._get_mcp_app") as mock_get:
            mock_app = MagicMock()
            mock_get.return_value = mock_app
            from modules.root_mcp_main_entry import run_mcp_server
            run_mcp_server()
            mock_app.run.assert_called_once()
