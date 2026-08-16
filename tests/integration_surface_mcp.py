"""Unit test suite for MCP server tools and configuration."""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

import pytest

from modules.root_mcp_main_entry import (
    process_direct_prompt,
    process_prompt_file_only,
    setup_session,
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

    def test_process_direct_prompt_mock(self) -> None:
        """Test process_direct_prompt tool execution with mocked tools."""
        mock_tools = MagicMock()
        mock_tools.process_direct_prompt.return_value = "Mocked AI Response"
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            result = asyncio.run(process_direct_prompt("Hello Qwen", timeout_sec=30, headless=True))
            self.assertEqual(result, "Mocked AI Response")

    def test_process_prompt_file_only_success(self) -> None:
        """Test process_prompt_file_only with valid file input."""
        mock_tools = MagicMock()
        mock_tools.process_prompt_file_only.return_value = "Successfully processed prompt.md"
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            res = asyncio.run(process_prompt_file_only("/tmp/prompt.md", "/tmp/output.md"))
            self.assertIn("Successfully processed", res)

    def test_setup_session(self) -> None:
        """Test setup_session manual login trigger."""
        mock_tools = MagicMock()
        mock_tools.setup_session.return_value = "Browser session saved to 'x'"
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            res = asyncio.run(setup_session())
            self.assertIn("Browser session saved", res)

    def test_process_direct_prompt_auth_required_error(self) -> None:
        """Test process_direct_prompt returns clear error string when AuthRequiredError is raised."""
        mock_tools = MagicMock()
        mock_tools.process_direct_prompt.return_value = "ERROR [AUTH_REQUIRED]: No active login session found"
        with patch("modules.root_mcp_main_entry._get_tools", return_value=mock_tools):
            result = asyncio.run(process_direct_prompt("Test prompt", timeout_sec=30, headless=True))
            self.assertIn("ERROR [AUTH_REQUIRED]", result)
            self.assertIn("No active login session found", result)


if __name__ == "__main__":
    unittest.main()
