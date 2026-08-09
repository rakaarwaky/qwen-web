"""Regression test suite for qwen_auto.py to prevent recurrence of fixed issues."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.types import AppConfig
from src.qwen_client import QwenClient
from src.pipeline import (
    _list_input_files,
    load_role_prompt,
    resolve_role_paths,
)


class TestQwenAutoRegression(unittest.TestCase):
    """Regression tests for event-driven parsing, role-based prompts, path resolution."""

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

    def test_regression_qwen_client_backward_compatible_init(self) -> None:
        """Verifies QwenClient accepts both old (ctx, cfg) and new interfaces."""
        mock_ctx = MagicMock()
        client_old = QwenClient(mock_ctx)
        self.assertIsNotNone(client_old)
        self.assertIsNotNone(client_old.context)

        cfg = AppConfig(
            mode="batch",
            input_path=Path("input"),
            output_path=Path("output"),
            done_path=Path("input/done"),
            failed_path=Path("input/failed"),
            proc_path=Path("input/.processing"),
            session_path=Path("qwen_session"),
        )
        client_new = QwenClient(None, cfg)
        self.assertIsNotNone(client_new)


if __name__ == "__main__":
    unittest.main()
