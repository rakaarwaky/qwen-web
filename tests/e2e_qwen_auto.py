"""E2E test suite for qwen_auto.py testing full request lifecycle."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.config import AppConfig, RunContext
from src.qwen_client import QwenClient
from src.pipeline import AuditLog, _process_file


class TestQwenAutoE2E(unittest.TestCase):
    """End-to-end tests for full request processing lifecycle."""

    def test_e2e_mock_browser_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            input_file = base / "e2e_prompt.md"
            input_file.write_text("# E2E Test Prompt\nExplain event-driven architecture.")

            out_file = base / "e2e_output.md"

            mock_ctx = MagicMock()
            mock_page = MagicMock()
            mock_ctx.pages = [mock_page]
            mock_ctx.new_page.return_value = mock_page

            # Setup page mock returns for DOM lifecycle
            mock_page.is_closed.return_value = False
            mock_page.title.return_value = "Qwen AI"
            mock_page.url = "https://chat.qwen.ai/c/test12345"

            # Mock locator for input and send button
            mock_locator = MagicMock()
            mock_locator.first = mock_locator
            mock_locator.all.return_value = [mock_locator]
            mock_locator.is_visible.return_value = True
            mock_locator.is_enabled.return_value = True
            mock_locator.count.return_value = 1
            mock_page.locator.return_value = mock_locator

            mock_fc_info = MagicMock()
            mock_fc = MagicMock()
            mock_fc_info.__enter__.return_value = mock_fc
            mock_fc.value = MagicMock()
            mock_page.expect_file_chooser.return_value = mock_fc_info

            # Mock page evaluate to simulate DOM states:
            # 1. _is_file_parsing_or_waiting -> False
            # 2. _is_prompt_dispatched -> True
            # 3. _latest_message_text -> Generated E2E Response Text
            def mock_evaluate(script, *args):
                if "error_selectors" in script or "cannot" in script:
                    return None
                if "Parsing..." in script or "waitKeywords" in script or "offline-banner" in script:
                    return False
                if "file-card-list" in script:
                    return True
                if "stopBtn" in script or "userMsgs" in script:
                    return True
                if "assistantNodes" in script or "selectors" in script:
                    return "Generated E2E Response Text from Qwen AI."
                return True

            mock_page.evaluate.side_effect = mock_evaluate

            client = QwenClient(mock_ctx, headless=True)
            res = client.send_file(input_file, timeout=10)
            self.assertEqual(res, "Generated E2E Response Text from Qwen AI.")


if __name__ == "__main__":
    unittest.main()
