"""Extended tests for main.py — covering _interactive_prompt, _run_manual_login, main()."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.root_cli_main_entry import (
    _build_config,
    _interactive_prompt,
    _run_manual_login,
    _run_watcher,
    main,
)
from modules.shared.src import AppConfig


class TestInteractivePrompt:
    def test_exit_choice(self):
        with patch("builtins.input", return_value="6"):
            result = _interactive_prompt()
            assert result is None

    def test_init_choice(self):
        with patch("builtins.input", return_value="5"), \
             patch("modules.main.run_init"):
            result = _interactive_prompt()
            assert result is None

    def test_login_choice(self):
        with patch("builtins.input", return_value="4"), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "login"

    def test_watcher_choice(self):
        with patch("builtins.input", side_effect=["1", "n"]), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "watcher"

    def test_batch_choice(self):
        with patch("builtins.input", side_effect=["2", "y"]), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "batch"

    def test_single_mode_with_files(self, tmp_path):
        todo = tmp_path / "todo" / "role-dev" / "todo"
        todo.mkdir(parents=True)
        (todo / "task.md").write_text("task")
        with patch("builtins.input", side_effect=["3", "1", "y"]), \
             patch("sys.stdin") as mock_stdin, \
             patch("modules.main.DEFAULT_TODO", tmp_path / "todo"):
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "single"

    def test_single_mode_no_files(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with patch("builtins.input", side_effect=["3", "", "", "y"]), \
             patch("sys.stdin") as mock_stdin, \
             patch("modules.main.DEFAULT_TODO", empty):
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "single"

    def test_single_mode_invalid_choice(self, tmp_path):
        todo = tmp_path / "todo" / "role-dev" / "todo"
        todo.mkdir(parents=True)
        (todo / "task.md").write_text("task")
        with patch("builtins.input", side_effect=["3", "abc", "y"]), \
             patch("sys.stdin") as mock_stdin, \
             patch("modules.main.DEFAULT_TODO", tmp_path / "todo"):
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "single"

    def test_single_mode_out_of_range(self, tmp_path):
        todo = tmp_path / "todo" / "role-dev" / "todo"
        todo.mkdir(parents=True)
        (todo / "task.md").write_text("task")
        with patch("builtins.input", side_effect=["3", "99", "y"]), \
             patch("sys.stdin") as mock_stdin, \
             patch("modules.main.DEFAULT_TODO", tmp_path / "todo"):
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "single"

    def test_not_tty_returns_none(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = _interactive_prompt()
            assert result is None

    def test_default_choice_is_watcher(self):
        with patch("builtins.input", side_effect=["", "n"]), \
             patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "watcher"


class TestRunManualLogin:
    def test_not_tty_exits(self):
        with patch("sys.stdin") as mock_stdin, \
             pytest.raises(SystemExit):
            mock_stdin.isatty.return_value = False
            cfg = AppConfig(
                mode="login",
                input_path=Path("/tmp/in"),
                output_path=Path("/tmp/out"),
                done_path=Path("/tmp/done"),
                failed_path=Path("/tmp/failed"),
                proc_path=Path("/tmp/proc"),
                session_path=Path("/tmp/session"),
            )
            _run_manual_login(cfg)

    def test_login_opens_browser(self):
        with patch("sys.stdin") as mock_stdin, \
             patch("modules.main.browser_session") as mock_bs, \
             patch("builtins.input", return_value=""):
            mock_stdin.isatty.return_value = True
            mock_page = MagicMock()
            mock_ctx = MagicMock()
            mock_ctx.pages = [mock_page]
            mock_bs.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)
            cfg = AppConfig(
                mode="login",
                input_path=Path("/tmp/in"),
                output_path=Path("/tmp/out"),
                done_path=Path("/tmp/done"),
                failed_path=Path("/tmp/failed"),
                proc_path=Path("/tmp/proc"),
                session_path=Path("/tmp/session"),
            )
            _run_manual_login(cfg)
            mock_page.goto.assert_called_once()


class TestRunWatcher:
    def test_processes_files(self, tmp_path):
        client = MagicMock()
        cfg = AppConfig(
            mode="watcher",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
            log_path=tmp_path / "log",
            interval=1,
        )
        audit = MagicMock()

        with patch("modules.main._iter_todo", return_value=iter([])), \
             patch("modules.main.StatusFileWriter") as mock_sw:
            _run_watcher(client, cfg, audit)
            mock_sw.return_value.write.assert_called()


class TestMain:
    def test_main_init(self, tmp_path):
        with patch("sys.argv", ["qwen-cli", "init", str(tmp_path)]):
            result = main()
            assert result == 0

    def test_main_interactive_exit(self):
        with patch("sys.argv", ["qwen-cli"]), \
             patch("modules.main._interactive_prompt", return_value=None):
            result = main()
            assert result == 0

    def test_main_login_mode(self):
        with patch("sys.argv", ["qwen-cli", "--login"]), \
             patch("modules.main._run_manual_login"), \
             patch("modules.main.setup_observability"):
            result = main()
            assert result == 0

    def test_main_batch_mode(self, tmp_path):
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        with patch("sys.argv", ["qwen-cli", "-i", str(in_dir), "-o", str(tmp_path / "out"), "--headless"]), \
             patch("modules.main.setup_observability"), \
             patch("modules.main.browser_session") as mock_bs, \
             patch("modules.main.QwenClient") as mock_client, \
             patch("modules.main._iter_todo", return_value=iter([])):
            mock_bs.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)
            result = main()
            assert result == 0

    def test_main_watcher_mode(self, tmp_path):
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        with patch("sys.argv", ["qwen-cli", "-i", str(in_dir), "-o", str(tmp_path / "out"), "--headless", "--watch"]), \
             patch("modules.main.setup_observability"), \
             patch("modules.main.browser_session") as mock_bs, \
             patch("modules.main.QwenClient") as mock_client, \
             patch("modules.main._run_watcher"):
            mock_bs.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)
            result = main()
            assert result == 0

    def test_main_auth_error(self, tmp_path):
        from modules.shared.src import AuthRequiredError
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        with patch("sys.argv", ["qwen-cli", "-i", str(in_dir), "-o", str(tmp_path / "out"), "--headless"]), \
             patch("modules.main.setup_observability"), \
             patch("modules.main.browser_session") as mock_bs, \
             patch("modules.main.QwenClient") as mock_client, \
             patch("modules.main._iter_todo", side_effect=AuthRequiredError("login")):
            mock_bs.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)
            result = main()
            assert result == 1

    def test_main_general_error(self, tmp_path):
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        with patch("sys.argv", ["qwen-cli", "-i", str(in_dir), "-o", str(tmp_path / "out"), "--headless"]), \
             patch("modules.main.setup_observability"), \
             patch("modules.main.browser_session") as mock_bs, \
             patch("modules.main.QwenClient") as mock_client, \
             patch("modules.main._iter_todo", side_effect=RuntimeError("boom")):
            mock_bs.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)
            result = main()
            assert result == 1
