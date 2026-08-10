"""Tests for mcp_server.py — MCP tool functions and helpers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp_server import (
    _get_mcp_app,
    _isolate_thread_event_loop,
    _register_tool,
    qwen_get_audit_log,
)


class TestGetMcpApp:
    def test_returns_app_when_available(self):
        with patch("src.mcp_server.mcp", new_callable=lambda: MagicMock):
            app = _get_mcp_app()
            assert app is not None

    def test_raises_when_mcp_none(self):
        with patch("src.mcp_server.mcp", None):
            with pytest.raises(ImportError, match="mcp"):
                _get_mcp_app()


class TestIsolateThreadEventLoop:
    def test_isolates_loop(self):
        _isolate_thread_event_loop()


class TestRegisterTool:
    def test_registers_with_mcp(self):
        mock_mcp = MagicMock()
        mock_mcp.tool.return_value = lambda fn: fn
        with patch("src.mcp_server.mcp", mock_mcp):
            @_register_tool
            async def my_func():
                return "ok"
            result = asyncio.get_event_loop().run_until_complete(my_func())
            assert result == "ok"

    def test_returns_fn_when_mcp_none(self):
        with patch("src.mcp_server.mcp", None):
            @_register_tool
            async def my_func():
                return "ok"
            result = asyncio.get_event_loop().run_until_complete(my_func())
            assert result == "ok"


class TestGetAuditLog:
    def test_no_log_file(self, tmp_path):
        with patch("src.mcp_server.DEFAULT_LOG", tmp_path):
            result = qwen_get_audit_log()
            assert "does not exist" in result

    def test_with_log_entries(self, tmp_path):
        log_file = tmp_path / "audit_history.jsonl"
        entries = [
            json.dumps({"run_id": "1", "status": "SUCCESS"}),
            json.dumps({"run_id": "2", "status": "FAILED"}),
        ]
        log_file.write_text("\n".join(entries) + "\n")
        with patch("src.mcp_server.DEFAULT_LOG", tmp_path):
            result = qwen_get_audit_log(limit=1)
            records = json.loads(result)
            assert len(records) == 1
            assert records[0]["run_id"] == "2"

    def test_empty_log_file(self, tmp_path):
        log_file = tmp_path / "audit_history.jsonl"
        log_file.write_text("")
        with patch("src.mcp_server.DEFAULT_LOG", tmp_path):
            result = qwen_get_audit_log()
            records = json.loads(result)
            assert len(records) == 0


class TestRunMcpServer:
    def test_run_mcp_server(self):
        with patch("src.mcp_server._get_mcp_app") as mock_get:
            mock_app = MagicMock()
            mock_get.return_value = mock_app
            from src.mcp_server import run_mcp_server
            run_mcp_server()
            mock_app.run.assert_called_once()
