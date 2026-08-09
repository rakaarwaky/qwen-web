"""Regression test suite for qwen_auto.py to prevent recurrence of fixed issues."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.qwen_auto import (
    AppConfig,
    QwenClient,
    load_role_prompt,
    resolve_role_paths,
    _list_input_files,
)


class TestQwenAutoRegression(unittest.TestCase):
    """Regression tests for event-driven parsing, role-based prompts, path resolution, and reconnect logic."""

    def test_regression_user_prompt_filtered_from_assistant_response(self) -> None:
        """Verifies _latest_message_text filters out user prompt bubbles and only extracts assistant answers."""
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_ctx.pages = [mock_page]
        mock_page.is_closed.return_value = False

        client = QwenClient(mock_ctx, headless=True)

        def mock_eval(js_code, *args):
            if "userParent" in js_code:
                return "Filtered Assistant Response Only"
            return 0

        mock_page.evaluate.side_effect = mock_eval
        text = client._latest_message_text(baseline=0)
        self.assertEqual(text, "Filtered Assistant Response Only")

    def test_regression_parsing_indicator_blocks_send(self) -> None:
        """Verifies _is_file_parsing_or_waiting returns True when 'Parsing...' string is present in DOM."""
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_ctx.pages = [mock_page]
        mock_page.is_closed.return_value = False

        client = QwenClient(mock_ctx, headless=True)

        def mock_eval(js_code, *args):
            if "waitKeywords" in js_code:
                return True
            return False

        mock_page.evaluate.side_effect = mock_eval
        self.assertTrue(client._is_file_parsing_or_waiting())

    def test_regression_dynamic_role_prompt_loading(self) -> None:
        """Verifies load_role_prompt loads PROMPT.md dynamically from role path and strips frontmatter."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            role_dir = base / "role-architect" / "todo"
            role_dir.mkdir(parents=True, exist_ok=True)

            prompt_file = base / "role-architect" / "PROMPT.md"
            prompt_file.write_text(
                "---\nname: role-architect\n---\n# Architect Custom Role Prompt Instructions"
            )

            file_path = role_dir / "gateway_v1.7.0.md"
            file_path.write_text("Document body content")

            loaded = load_role_prompt(file_path)
            self.assertIn("# Architect Custom Role Prompt Instructions", loaded)
            self.assertNotIn("name: role-architect", loaded)

    def test_regression_resolve_role_paths(self) -> None:
        """Verifies resolve_role_paths resolves role subfolders and strips redundant todo path segments."""
        cfg = AppConfig(
            mode="batch",
            input_path=Path("input"),
            output_path=Path("output"),
            done_path=Path("input/done"),
            failed_path=Path("input/failed"),
            proc_path=Path("input/.processing"),
            session_path=Path("session"),
        )

        rel = Path("role-architect/todo/gateway_v1.7.0.md")
        out_p, done_p, fail_p, proc_p = resolve_role_paths(rel, cfg)

        self.assertTrue(str(out_p).endswith("output/role-architect/gateway_v1.7.0.md"))
        self.assertTrue(str(done_p).endswith("role-architect/done/gateway_v1.7.0.md"))
        self.assertTrue(str(fail_p).endswith("role-architect/failed/gateway_v1.7.0.md"))
        self.assertTrue(str(proc_p).endswith("role-architect/.processing/gateway_v1.7.0.md"))

    def test_regression_prompt_md_excluded_from_queue(self) -> None:
        """Verifies PROMPT.md and internal folders (.processing, done, failed) are excluded from file queue."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            role_dir = base / "role-architect"
            role_dir.mkdir(parents=True, exist_ok=True)

            (role_dir / "PROMPT.md").write_text("Prompt config")
            (role_dir / "doc1.md").write_text("Doc 1")
            
            done_dir = role_dir / "done"
            done_dir.mkdir(parents=True, exist_ok=True)
            (done_dir / "old.md").write_text("Old completed doc")

            files = _list_input_files(base)
            rel_files = [str(rel) for _, rel in files]

            self.assertIn("role-architect/doc1.md", rel_files)
            self.assertNotIn("role-architect/PROMPT.md", rel_files)
            self.assertNotIn("role-architect/done/old.md", rel_files)

    def test_regression_max_reconnect_loop_prevention(self) -> None:
        """Verifies _wait_for_response caps reconnect attempts at max_reconnects (5) to prevent infinite loops."""
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_ctx.pages = [mock_page]
        mock_page.is_closed.return_value = False

        client = QwenClient(mock_ctx, headless=True)

        def mock_eval(js_code, *args):
            if "reconnect" in js_code:
                return True  # Reconnection banner visible
            return ""

        mock_page.evaluate.side_effect = mock_eval
        # Should attempt 5 reconnects then finish gracefully without crashing
        res = client._wait_for_response(baseline=0, timeout=1)
        self.assertEqual(mock_page.reload.call_count, 5)


if __name__ == "__main__":
    unittest.main()
