"""Tests for main.py — CLI argument parsing, config building, run_init."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from modules.core.src.root_core_container import SharedContainer
from modules.root_cli_main_entry import (
    _build_config,
    _parse_args,
)


class TestParseArgs:
    def test_default_args(self):
        with patch("sys.argv", ["qwen-cli"]):
            args = _parse_args()
            assert args.headless is False
            assert args.watch is False
            assert args.login is False

    def test_headless_flag(self):
        with patch("sys.argv", ["qwen-cli", "--headless"]):
            args = _parse_args()
            assert args.headless is True

    def test_watch_flag(self):
        with patch("sys.argv", ["qwen-cli", "--watch"]):
            args = _parse_args()
            assert args.watch is True

    def test_login_flag(self):
        with patch("sys.argv", ["qwen-cli", "--login"]):
            args = _parse_args()
            assert args.login is True

    def test_mcp_flag(self):
        with patch("sys.argv", ["qwen-cli", "--mcp"]):
            args = _parse_args()
            assert args.mcp is True

    def test_timeout_override(self):
        with patch("sys.argv", ["qwen-cli", "--timeout", "60"]):
            args = _parse_args()
            assert args.timeout == 60

    def test_retry_failed(self):
        with patch("sys.argv", ["qwen-cli", "--retry-failed"]):
            args = _parse_args()
            assert args.retry_failed is True

    def test_custom_paths(self, tmp_path):
        with patch("sys.argv", ["qwen-cli", "-i", str(tmp_path / "in"), "-o", str(tmp_path / "out")]):
            args = _parse_args()
            assert args.input == str(tmp_path / "in")
            assert args.output == str(tmp_path / "out")


class TestBuildConfig:
    def test_batch_mode(self, tmp_path):
        args = MagicMock()
        args.login = False
        args.watch = False
        args.input = str(tmp_path)
        args.output = str(tmp_path / "out")
        args.done_dir = str(tmp_path / "done")
        args.failed_dir = str(tmp_path / "failed")
        args.proc_dir = str(tmp_path / "proc")
        args.data_dir = str(tmp_path / "session")
        args.log_dir = str(tmp_path / "log")
        args.headless = True
        args.timeout = 300
        args.interval = 3
        args.request_timeout = 120
        args.poll_interval = 1.0
        args.streaming_timeout = 180
        args.rate_limit = 60
        args.cb_threshold = 5
        args.cb_window = 30
        args.retry_failed = False

        cfg = _build_config(args)
        assert cfg.mode == "batch"
        assert cfg.headless is True

    def test_watcher_mode(self, tmp_path):
        args = MagicMock()
        args.login = False
        args.watch = True
        input_dir = tmp_path / "in"
        input_dir.mkdir()
        args.input = str(input_dir)
        args.output = str(tmp_path / "out")
        args.done_dir = str(tmp_path / "done")
        args.failed_dir = str(tmp_path / "failed")
        args.proc_dir = str(tmp_path / "proc")
        args.data_dir = str(tmp_path / "session")
        args.log_dir = str(tmp_path / "log")
        args.headless = False
        args.timeout = 300
        args.interval = 5
        args.request_timeout = 120
        args.poll_interval = 1.0
        args.streaming_timeout = 180
        args.rate_limit = 60
        args.cb_threshold = 5
        args.cb_window = 30
        args.retry_failed = False

        cfg = _build_config(args)
        assert cfg.mode == "watcher"

    def test_login_mode(self, tmp_path):
        args = MagicMock()
        args.login = True
        args.watch = False
        args.input = str(tmp_path / "in")
        args.output = str(tmp_path / "out")
        args.done_dir = str(tmp_path / "done")
        args.failed_dir = str(tmp_path / "failed")
        args.proc_dir = str(tmp_path / "proc")
        args.data_dir = str(tmp_path / "session")
        args.log_dir = str(tmp_path / "log")
        args.headless = False
        args.timeout = 300
        args.interval = 3
        args.request_timeout = 120
        args.poll_interval = 1.0
        args.streaming_timeout = 180
        args.rate_limit = 60
        args.cb_threshold = 5
        args.cb_window = 30
        args.retry_failed = False

        cfg = _build_config(args)
        assert cfg.mode == "login"

    def test_single_file_mode(self, tmp_path):
        args = MagicMock()
        args.login = False
        args.watch = False
        single_file = tmp_path / "task.md"
        single_file.write_text("task")
        args.input = str(single_file)
        args.output = str(tmp_path / "out")
        args.done_dir = str(tmp_path / "done")
        args.failed_dir = str(tmp_path / "failed")
        args.proc_dir = str(tmp_path / "proc")
        args.data_dir = str(tmp_path / "session")
        args.log_dir = str(tmp_path / "log")
        args.headless = False
        args.timeout = 300
        args.interval = 3
        args.request_timeout = 120
        args.poll_interval = 1.0
        args.streaming_timeout = 180
        args.rate_limit = 60
        args.cb_threshold = 5
        args.cb_window = 30
        args.retry_failed = False

        cfg = _build_config(args)
        assert cfg.mode == "single"


class TestRunInit:
    def test_creates_skill_md(self, tmp_path):
        with (
            patch("modules.core.src.capabilities_workspace_provisioner.BASE_DIR", tmp_path),
            patch("modules.core.src.capabilities_workspace_provisioner.XDG_SKILL_MD", tmp_path / "nonexistent"),
        ):
            skill_dir = tmp_path / ".agents" / "skills" / "qwen-web"
            assert not skill_dir.exists()
            SharedContainer().core.init_workspace(tmp_path)
            assert (skill_dir / "SKILL.md").exists()

    def test_creates_gitignore(self, tmp_path):
        with (
            patch("modules.core.src.capabilities_workspace_provisioner.BASE_DIR", tmp_path),
            patch("modules.core.src.capabilities_workspace_provisioner.XDG_SKILL_MD", tmp_path / "nonexistent"),
        ):
            SharedContainer().core.init_workspace(tmp_path)
            gitignore = tmp_path / ".gitignore"
            assert gitignore.exists()
            assert ".qwen-web/" in gitignore.read_text()

    def test_appends_to_existing_gitignore(self, tmp_path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")
        with (
            patch("modules.core.src.capabilities_workspace_provisioner.BASE_DIR", tmp_path),
            patch("modules.core.src.capabilities_workspace_provisioner.XDG_SKILL_MD", tmp_path / "nonexistent"),
        ):
            SharedContainer().core.init_workspace(tmp_path)
            content = gitignore.read_text()
            assert ".qwen-web/" in content
            assert "*.pyc" in content

    def test_creates_symlinks(self, tmp_path):
        xdg_input = tmp_path / "xdg" / "input"
        xdg_output = tmp_path / "xdg" / "output"
        xdg_log = tmp_path / "xdg" / "log"
        for d in (xdg_input, xdg_output, xdg_log):
            d.mkdir(parents=True, exist_ok=True)
        with (
            patch("modules.core.src.capabilities_workspace_provisioner.BASE_DIR", tmp_path),
            patch("modules.core.src.capabilities_workspace_provisioner.XDG_SKILL_MD", tmp_path / "nonexistent"),
            patch("modules.core.src.capabilities_workspace_provisioner.DEFAULT_OUTPUT", xdg_output),
            patch("modules.core.src.capabilities_workspace_provisioner.DEFAULT_LOG", xdg_log),
        ):
            SharedContainer().core.init_workspace(tmp_path)
            dot_qwen = tmp_path / ".qwen-web"
            assert dot_qwen.exists()
            assert (dot_qwen / "output").exists()
            assert (dot_qwen / "log").exists()


class TestCliValidation:
    def test_login_precedes_watch_and_path_inference(self, tmp_path):
        args = _namespace_for_config(tmp_path, login=True, watch=True, input_path=tmp_path / "missing")
        cfg = _build_config(args)
        assert cfg.mode == "login"
        assert cfg.headless is False

    def test_watch_requires_existing_directory(self, tmp_path):
        args = _namespace_for_config(tmp_path, watch=True, input_path=tmp_path / "missing")
        with pytest.raises(ValueError, match="existing directory"):
            _build_config(args)

    def test_extensionless_existing_file_is_single_mode(self, tmp_path):
        input_file = tmp_path / "prompt"
        input_file.write_text("prompt")
        args = _namespace_for_config(tmp_path, input_path=input_file)
        assert _build_config(args).mode == "single"

    def test_missing_input_is_rejected(self, tmp_path):
        args = _namespace_for_config(tmp_path, input_path=tmp_path / "missing")
        with pytest.raises(ValueError, match="existing file or directory"):
            _build_config(args)


def _namespace_for_config(tmp_path, *, login=False, watch=False, input_path=None):
    from argparse import Namespace

    return Namespace(
        login=login,
        watch=watch,
        input=str(input_path or tmp_path),
        output=str(tmp_path / "out"),
        done_dir=str(tmp_path / "done"),
        failed_dir=str(tmp_path / "failed"),
        proc_dir=str(tmp_path / "proc"),
        data_dir=str(tmp_path / "session"),
        log_dir=str(tmp_path / "log"),
        headless=True,
        timeout=300,
        interval=3,
        request_timeout=120,
        poll_interval=1.0,
        streaming_timeout=180,
        rate_limit=60,
        cb_threshold=5,
        cb_window=30,
        retry_failed=False,
    )
