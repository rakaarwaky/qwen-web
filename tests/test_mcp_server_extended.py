"""Tests for mcp_server.py — MCP tool functions and helpers."""

from __future__ import annotations

import asyncio
import inspect
import io
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

from modules.root_mcp_main_entry import (
    GENERATED_TOOLS,
    MCP_TOOL_SPECS,
    _get_mcp_app,
    _register_tool,
    _register_tools,
    qwen_get_audit_log,
    qwen_send_prompt,
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
            result = asyncio.run(qwen_get_audit_log())
            assert "does not exist" in result

    def test_with_log_entries(self, tmp_path):
        entries = [
            json.dumps({"run_id": "1", "status": "SUCCESS"}),
            json.dumps({"run_id": "2", "status": "FAILED"}),
        ]
        mock_tools = MagicMock()
        mock_tools.get_audit_log.return_value = "[" + ",".join(entries) + "]"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            result = asyncio.run(qwen_get_audit_log(limit=1))
            records = json.loads(result)
            assert len(records) == 2

    def test_empty_log_file(self, tmp_path):
        mock_tools = MagicMock()
        mock_tools.get_audit_log.return_value = "[]"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            result = asyncio.run(qwen_get_audit_log())
            records = json.loads(result)
            assert len(records) == 0


class TestMcpRegistration:
    def test_audit_log_is_declared_and_generated(self):
        audit_spec = next(spec for spec in MCP_TOOL_SPECS if spec["name"] == "qwen_get_audit_log")
        assert audit_spec["method"] == "get_audit_log"
        assert audit_spec["params"] == [("limit", "int", False, 20)]
        handler = GENERATED_TOOLS["qwen_get_audit_log"]
        assert inspect.iscoroutinefunction(handler)
        assert inspect.signature(handler).parameters["limit"].default == 20

    def test_registers_every_spec_once(self):
        mock_app = MagicMock()
        registered = []

        def register(fn):
            registered.append(fn.__name__)
            return fn

        mock_app.tool.return_value = register
        with patch("modules.root_mcp_main_entry._get_mcp_app", return_value=mock_app):
            _register_tools()

        expected = [spec["name"] for spec in MCP_TOOL_SPECS]
        assert registered == expected
        assert registered.count("qwen_get_audit_log") == 1


class TestRunMcpServer:
    def test_run_mcp_server(self):
        with patch("modules.root_mcp_main_entry._get_mcp_app") as mock_get:
            mock_app = MagicMock()
            mock_get.return_value = mock_app
            from modules.root_mcp_main_entry import run_mcp_server

            run_mcp_server()
            mock_app.run.assert_called_once()

    def test_tool_output_is_isolated_from_json_rpc_stdout(self):
        transport_stdout = io.StringIO()
        diagnostics_stderr = io.StringIO()
        tools = MagicMock()

        def send_prompt(*args, **kwargs):
            print("tool execution noise")
            sys.stdout.writelines(["line1\n", "line2\n"])
            sys.stdout.buffer.write(b"binary data\n")
            return "AI answer"

        tools.send_prompt.side_effect = send_prompt
        mock_app = MagicMock()
        mock_app.tool.return_value = lambda fn: fn

        def run_transport():
            print("json-rpc transport output")
            assert asyncio.run(qwen_send_prompt("hello")) == "AI answer"

        mock_app.run.side_effect = run_transport
        with (
            patch("modules.root_mcp_main_entry._get_mcp_app", return_value=mock_app),
            patch("modules.root_mcp_main_entry._tools", return_value=tools),
            patch("modules.core.src.capabilities_observability_setup.ObservabilitySetup.setup_observability"),
            patch.object(sys, "stdout", transport_stdout),
            patch.object(sys, "stderr", diagnostics_stderr),
        ):
            from modules.root_mcp_main_entry import run_mcp_server

            run_mcp_server()

        assert "json-rpc transport output" in transport_stdout.getvalue()
        assert "tool execution noise" not in transport_stdout.getvalue()
        assert "tool execution noise" in diagnostics_stderr.getvalue()
        assert "line1" in diagnostics_stderr.getvalue()
        assert "line2" in diagnostics_stderr.getvalue()
        assert b"binary data" in diagnostics_stderr.buffer.getvalue()
        assert sys.stdout is transport_stdout

    def test_stdout_restored_after_app_run_exception(self):
        transport_stdout = io.StringIO()
        diagnostics_stderr = io.StringIO()
        mock_app = MagicMock()
        mock_app.tool.return_value = lambda fn: fn
        mock_app.run.side_effect = RuntimeError("app.run failed")

        with (
            patch("modules.root_mcp_main_entry._get_mcp_app", return_value=mock_app),
            patch("modules.core.src.capabilities_observability_setup.ObservabilitySetup.setup_observability"),
            patch.object(sys, "stdout", transport_stdout),
            patch.object(sys, "stderr", diagnostics_stderr),
        ):
            from modules.root_mcp_main_entry import run_mcp_server

            with pytest.raises(RuntimeError, match="app.run failed"):
                run_mcp_server()

        assert sys.stdout is transport_stdout
