"""Unit test suite for src/mcp_server.py tools and MCP server configuration."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp_server import (
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
        dummy_log = Path(tempfile.gettempdir()) / "non_existent_log_dir_12345"
        with patch("src.mcp_server.DEFAULT_LOG", dummy_log):
            res = qwen_get_audit_log()
            self.assertEqual(res, "Audit log file does not exist yet.")

    def test_qwen_get_audit_log_records(self) -> None:
        """Test qwen_get_audit_log returns formatted JSON list."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_dir = Path(tmp_dir)
            audit_file = log_dir / "audit_history.jsonl"
            rec = {"run_id": "test1234", "status": "SUCCESS", "duration_sec": 1.2}
            audit_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")

            with patch("src.mcp_server.DEFAULT_LOG", log_dir):
                res = qwen_get_audit_log(limit=5)
                data = json.loads(res)
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["run_id"], "test1234")

    @patch("src.mcp_server.QwenClient")
    @patch("src.mcp_server.browser_session")
    def test_qwen_send_prompt_mock(self, mock_browser_session: MagicMock, mock_qwen_client: MagicMock) -> None:
        """Test qwen_send_prompt tool execution with mocked browser and client."""
        mock_ctx = MagicMock()
        mock_browser_session.return_value.__enter__.return_value = mock_ctx

        client_inst = MagicMock()
        client_inst.send_file.return_value = "Mocked AI Response"
        mock_qwen_client.return_value = client_inst

        result = asyncio.run(qwen_send_prompt("Hello Qwen", timeout_sec=30, headless=True))
        self.assertEqual(result, "Mocked AI Response")
        client_inst.send_file.assert_called_once()

    @patch("src.mcp_server._process_file")
    @patch("src.mcp_server.QwenClient")
    @patch("src.mcp_server.browser_session")
    def test_qwen_process_single_success(self, mock_browser_session: MagicMock, mock_qwen_client: MagicMock, mock_process_file: MagicMock) -> None:
        """Test qwen_process_single with valid file input."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            in_file = Path(tmp_dir) / "prompt.md"
            out_file = Path(tmp_dir) / "output.md"
            in_file.write_text("Test prompt text", encoding="utf-8")

            res = asyncio.run(qwen_process_single(str(in_file), str(out_file)))
            self.assertIn("Successfully processed", res)
            mock_process_file.assert_called_once()

    @patch("src.mcp_server.browser_session")
    def test_qwen_setup_session(self, mock_browser_session: MagicMock) -> None:
        """Test qwen_setup_session manual login trigger."""
        mock_bctx = MagicMock()
        mock_page = MagicMock()
        mock_bctx.pages = [mock_page]
        mock_browser_session.return_value.__enter__.return_value = mock_bctx

        res = asyncio.run(qwen_setup_session())
        self.assertIn("Browser session saved", res)
        mock_page.goto.assert_called_once()

    @patch("src.mcp_server.QwenClient")
    @patch("src.mcp_server.browser_session")
    def test_qwen_send_prompt_auth_required_error(self, mock_browser_session: MagicMock, mock_qwen_client: MagicMock) -> None:
        """Test qwen_send_prompt returns clear error string when AuthRequiredError is raised."""
        from src.types import AuthRequiredError
        mock_ctx = MagicMock()
        mock_browser_session.return_value.__enter__.return_value = mock_ctx

        client_inst = MagicMock()
        client_inst.send_file.side_effect = AuthRequiredError("No active login session found")
        mock_qwen_client.return_value = client_inst

        result = asyncio.run(qwen_send_prompt("Test prompt", timeout_sec=30, headless=True))
        self.assertIn("ERROR [AUTH_REQUIRED]", result)
        self.assertIn("No active login session found", result)


if __name__ == "__main__":
    unittest.main()
