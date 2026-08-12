"""Regression tests for role prompt include-only approach.

Verifies:
- _get_role_search_directories uses include-only (closest ancestor role dir first)
- load_role_prompt resolves PROMPT.md from correct role directory
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.pipeline import (
    _get_role_search_directories,
    load_role_prompt,
)

ROLE = "role-test"


# ─── _get_role_search_directories — include-only approach ──────────────────


class TestGetRoleSearchDirectories:
    def test_todo_file_finds_closest_ancestor_role_dir(self, tmp_path: Path):
        """role-test/todo/file.md → searches role-test first."""
        input_root = tmp_path / "input"
        role_dir = input_root / ROLE
        role_dir.mkdir(parents=True)
        (role_dir / "PROMPT.md").write_text("role prompt", encoding="utf-8")

        file_path = role_dir / "todo" / "task.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("task content", encoding="utf-8")

        rel = Path(f"{ROLE}/todo/task.md")
        dirs = _get_role_search_directories(file_path, rel)
        # First entry should be the role directory itself
        assert role_dir in dirs

    def test_todo_nested_finds_parent_role_dir(self, tmp_path: Path):
        """role-test/todo/subdir/file.md → searches role-test."""
        input_root = tmp_path / "input"
        role_dir = input_root / ROLE
        role_dir.mkdir(parents=True)
        (role_dir / "PROMPT.md").write_text("role prompt", encoding="utf-8")

        file_path = role_dir / "todo" / "subdir" / "task.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("task content", encoding="utf-8")

        rel = Path(f"{ROLE}/todo/subdir/task.md")
        dirs = _get_role_search_directories(file_path, rel)
        assert role_dir in dirs

    def test_no_rel_path_returns_abs_parent(self):
        """When rel_path is None, returns file's absolute parent and ancestors."""
        p = Path("/tmp/project/file.md")
        dirs = _get_role_search_directories(p, None)
        assert Path("/tmp/project") in dirs

    def test_empty_rel_path_returns_abs_parent(self):
        """When rel_path is empty, returns file's absolute parent and ancestors."""
        p = Path("/tmp/project/file.md")
        dirs = _get_role_search_directories(p, Path(""))
        assert Path("/tmp/project") in dirs

    def test_role_root_finds_root(self, tmp_path: Path):
        """role-test/file.md → searches role-test."""
        input_root = tmp_path / "input"
        role_dir = input_root / ROLE
        role_dir.mkdir(parents=True)
        (role_dir / "PROMPT.md").write_text("role prompt", encoding="utf-8")

        file_path = role_dir / "task.md"
        file_path.write_text("task content", encoding="utf-8")

        rel = Path(f"{ROLE}/task.md")
        dirs = _get_role_search_directories(file_path, rel)
        assert role_dir in dirs

    def test_duplicate_dirs_filtered(self):
        """No duplicate role directories in search list."""
        p = Path("/tmp/test.md")
        rel = Path(f"{ROLE}/todo/file.md")
        dirs = _get_role_search_directories(p, rel)
        assert len(dirs) == len(set(dirs))


# ─── load_role_prompt — include-only resolution ──────────────────────────


class TestLoadRolePrompt:
    @pytest.fixture()
    def tmp_input(self, tmp_path: Path):
        """Create a temporary input/role-test structure."""
        role_dir = tmp_path / "input" / ROLE
        role_dir.mkdir(parents=True)
        (role_dir / "PROMPT.md").write_text(
            "---\ntitle: test\n---\nTest role instructions",
            encoding="utf-8",
        )
        todo_dir = role_dir / "todo"
        todo_dir.mkdir()
        return tmp_path

    def test_loads_from_closest_ancestor_role_dir(self, tmp_input: Path):
        """File in todo/ loads PROMPT.md from role dir, not todo dir."""
        file_path = tmp_input / "input" / ROLE / "todo" / "task.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("Process this task", encoding="utf-8")

        with patch("src.pipeline.DEFAULT_TODO", tmp_input / "input"):
            result = load_role_prompt(file_path, rel_path=Path(f"{ROLE}/todo/task.md"))

        assert "Test role instructions" in result
        # Should NOT include content from todo dir (no PROMPT.md there)
        assert "Process this task" not in result

    def test_no_role_prompt_returns_empty(self, tmp_input: Path):
        """When no PROMPT.md exists, returns empty string."""
        file_path = tmp_input / "input" / ROLE / "todo" / "task.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("Task content", encoding="utf-8")

        # Remove PROMPT.md if it exists
        prompt_file = tmp_input / "input" / ROLE / "PROMPT.md"
        if prompt_file.exists():
            prompt_file.unlink()

        with patch("src.pipeline.DEFAULT_TODO", tmp_input / "input"):
            result = load_role_prompt(file_path, rel_path=Path(f"{ROLE}/todo/task.md"))

        assert result == ""
