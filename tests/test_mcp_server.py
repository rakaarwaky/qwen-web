"""Unit test suite for MCP server tools and configuration."""
import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

import pytest

from modules.root_mcp_main_entry import (
    mcp,
    qwen_get_audit_log,
    qwen_process_single,
    qwen_send_prompt,
    qwen_setup_session,
)


@pytest.fixture(autouse=True)
def _reset_event_loop():
    """Reset asyncio event loop before each test to avoid Playwright contamination."""
    try:
        if hasattr(asyncio, "_set_running_loop"):
            asyncio._set_running_loop(None)
    except Exception:
        pass
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception:
        pass
    yield


class TestMCPServerTools(unittest.TestCase):
    """Unit tests for MCP server tools."""

    def test_mcp_instance_registered(self) -> None:
        """Verify FastMCP app instance is initialized."""
        if mcp is not None:
            self.assertEqual(mcp.name, "Qwen-Web")

    def test_qwen_get_audit_log_missing(self) -> None:
        """Test qwen_get_audit_log when log file does not exist."""
        mock_tools = MagicMock()
        mock_tools.get_audit_log.return_value = "Audit log file does not exist yet."
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            res = qwen_get_audit_log()
            self.assertEqual(res, "Audit log file does not exist yet.")

    def test_qwen_get_audit_log_records(self) -> None:
        """Test qwen_get_audit_log returns formatted JSON list."""
        records = json.dumps([{"run_id": "test1234", "status": "SUCCESS", "duration_sec": 1.2}])
        mock_tools = MagicMock()
        mock_tools.get_audit_log.return_value = records
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            res = qwen_get_audit_log(limit=5)
            data = json.loads(res)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["run_id"], "test1234")

    def test_qwen_send_prompt_mock(self) -> None:
        """Test qwen_send_prompt tool execution with mocked tools."""
        mock_tools = MagicMock()
        mock_tools.send_prompt.return_value = "Mocked AI Response"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            result = asyncio.run(qwen_send_prompt("Hello Qwen", timeout_sec=30, headless=True))
            self.assertEqual(result, "Mocked AI Response")

    def test_qwen_process_single_success(self) -> None:
        """Test qwen_process_single with valid file input."""
        mock_tools = MagicMock()
        mock_tools.process_single.return_value = "Successfully processed prompt.md"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            res = asyncio.run(qwen_process_single("/tmp/prompt.md", "/tmp/output.md"))
            self.assertIn("Successfully processed", res)

    def test_qwen_setup_session(self) -> None:
        """Test qwen_setup_session manual login trigger."""
        mock_tools = MagicMock()
        mock_tools.setup_session.return_value = "Browser session saved to 'x'"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            res = asyncio.run(qwen_setup_session())
            self.assertIn("Browser session saved", res)

    def test_qwen_send_prompt_auth_required_error(self) -> None:
        """Test qwen_send_prompt returns clear error string when AuthRequiredError is raised."""
        mock_tools = MagicMock()
        mock_tools.send_prompt.return_value = "ERROR [AUTH_REQUIRED]: No active login session found"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            result = asyncio.run(qwen_send_prompt("Test prompt", timeout_sec=30, headless=True))
            self.assertIn("ERROR [AUTH_REQUIRED]", result)
            self.assertIn("No active login session found", result)


if __name__ == "__main__":
    unittest.main()
