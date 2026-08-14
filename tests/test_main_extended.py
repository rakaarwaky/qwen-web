"""Extended tests for main.py — covering _interactive_prompt, _run_manual_login, main()."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.cli.src.surface_cli_interactive_controller import InteractiveController
from modules.core.src.agent_core_orchestrator import CoreOrchestrator
from modules.root_cli_main_entry import (
    _interactive_prompt,
    main,
)
from modules.shared.src import AppConfig


class TestInteractivePrompt:
    def test_exit_choice(self):
        with patch("builtins.input", return_value="6"):
            result = _interactive_prompt()
            assert result is None

    def test_init_choice(self):
        with patch("builtins.input", return_value="5"), patch.object(CoreOrchestrator, "init_workspace"):
            result = _interactive_prompt()
            assert result is None

    def test_login_choice(self):
        with patch("builtins.input", return_value="4"), patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "login"

    def test_watcher_choice(self):
        with patch("builtins.input", side_effect=["1", "n"]), patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "watcher"

    def test_batch_choice(self):
        with patch("builtins.input", side_effect=["2", "y"]), patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "batch"

    def test_single_mode_with_files(self, tmp_path):
        todo = tmp_path / "todo" / "role-dev" / "todo"
        todo.mkdir(parents=True)
        (todo / "task.md").write_text("task")
        with (
            patch("builtins.input", side_effect=["3", "1", "y"]),
            patch("sys.stdin") as mock_stdin,
            patch("modules.root_cli_main_entry.DEFAULT_TODO", tmp_path / "todo"),
            patch(
                "modules.cli.src.surface_cli_interactive_controller.list_input_files",
                return_value=[(todo / "task.md", Path("task.md"))],
            ),
        ):
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "single"

    def test_single_mode_no_files(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with (
            patch("builtins.input", side_effect=["3", "", "", "y"]),
            patch("sys.stdin") as mock_stdin,
            patch("modules.root_cli_main_entry.DEFAULT_TODO", empty),
        ):
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "single"

    def test_single_mode_invalid_choice(self, tmp_path):
        todo = tmp_path / "todo" / "role-dev" / "todo"
        todo.mkdir(parents=True)
        (todo / "task.md").write_text("task")
        with (
            patch("builtins.input", side_effect=["3", "abc", "y"]),
            patch("sys.stdin") as mock_stdin,
            patch("modules.root_cli_main_entry.DEFAULT_TODO", tmp_path / "todo"),
            patch(
                "modules.cli.src.surface_cli_interactive_controller.list_input_files",
                return_value=[(todo / "task.md", Path("task.md"))],
            ),
        ):
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "single"

    def test_single_mode_out_of_range(self, tmp_path):
        todo = tmp_path / "todo" / "role-dev" / "todo"
        todo.mkdir(parents=True)
        (todo / "task.md").write_text("task")
        with (
            patch("builtins.input", side_effect=["3", "99", "y"]),
            patch("sys.stdin") as mock_stdin,
            patch("modules.root_cli_main_entry.DEFAULT_TODO", tmp_path / "todo"),
            patch(
                "modules.cli.src.surface_cli_interactive_controller.list_input_files",
                return_value=[(todo / "task.md", Path("task.md"))],
            ),
        ):
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
        with patch("builtins.input", side_effect=["", "n"]), patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = True
            result = _interactive_prompt()
            assert result is not None
            assert result.mode == "watcher"


class TestInteractiveControllerRun:
    def test_non_tty_returns_validation_error(self):
        with patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = InteractiveController(MagicMock()).run()
        assert result["success"] is False
        assert result["category"] == "validation_error"
        assert result["ref"] == "cli-400"

    def test_explicit_exit_returns_success(self):
        with patch("sys.stdin") as mock_stdin, patch("builtins.input", return_value="6"):
            mock_stdin.isatty.return_value = True
            result = InteractiveController(MagicMock()).run()
        assert result == {"success": True, "message": "Exited."}


class TestRunManualLogin:
    def test_not_tty_exits(self):
        with (
            patch("sys.stdin") as mock_stdin,
            patch(
                "modules.cli.src.surface_cli_login_command.handle",
                return_value={"success": False, "error": "TTY required"},
            ) as mock_handle,
        ):
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
            from modules.root_cli_main_entry import _run_manual_login

            result = _run_manual_login(cfg)
            mock_handle.assert_called_once()
            assert result == 1

    def test_login_opens_browser(self):
        with (
            patch("sys.stdin") as mock_stdin,
            patch(
                "modules.cli.src.surface_cli_login_command.handle", return_value={"success": True, "message": "ok"}
            ) as mock_handle,
        ):
            mock_stdin.isatty.return_value = True
            cfg = AppConfig(
                mode="login",
                input_path=Path("/tmp/in"),
                output_path=Path("/tmp/out"),
                done_path=Path("/tmp/done"),
                failed_path=Path("/tmp/failed"),
                proc_path=Path("/tmp/proc"),
                session_path=Path("/tmp/session"),
            )
            from modules.root_cli_main_entry import _run_manual_login

            result = _run_manual_login(cfg)
            mock_handle.assert_called_once()
            assert result == 0

    def test_failure_prints_error_to_stderr(self, capsys):
        with patch(
            "modules.cli.src.surface_cli_login_command.handle",
            return_value={"success": False, "error": "Manual login requires an interactive terminal (TTY)"},
        ):
            cfg = AppConfig(
                mode="login",
                input_path=Path("/tmp/in"),
                output_path=Path("/tmp/out"),
                done_path=Path("/tmp/done"),
                failed_path=Path("/tmp/failed"),
                proc_path=Path("/tmp/proc"),
                session_path=Path("/tmp/session"),
            )
            from modules.root_cli_main_entry import _run_manual_login

            result = _run_manual_login(cfg)
            captured = capsys.readouterr()
            assert "Manual login requires an interactive terminal (TTY)" in captured.err
            assert result == 1


class TestMain:
    def test_main_init(self, tmp_path):
        with (
            patch("sys.argv", ["qwen-cli", "init", str(tmp_path)]),
            patch("modules.cli.src.surface_cli_init_command.handle", return_value={"success": True, "message": "ok"}),
        ):
            result = main()
            assert result == 0

    def test_main_interactive_exit(self):
        with (
            patch("sys.argv", ["qwen-cli"]),
            patch(
                "modules.cli.src.surface_cli_interactive_controller.InteractiveController.run",
                return_value={"success": True, "message": "Exited."},
            ) as mock_run,
        ):
            result = main()
            assert result == 0
            mock_run.assert_called_once_with()

    def test_main_non_tty_interactive_fails(self, capsys):
        with patch("sys.argv", ["qwen-cli"]), patch("sys.stdin") as mock_stdin:
            mock_stdin.isatty.return_value = False
            result = main()
            captured = capsys.readouterr()
            assert result == 1
            assert "Interactive mode requires a TTY" in captured.err

    def test_main_login_mode(self):
        with (
            patch("sys.argv", ["qwen-cli", "--login"]),
            patch("modules.root_cli_main_entry._run_manual_login", return_value=0),
        ):
            result = main()
            assert result == 0

    def test_main_login_mode_failure(self):
        with (
            patch("sys.argv", ["qwen-cli", "--login"]),
            patch("modules.root_cli_main_entry._run_manual_login", return_value=1),
        ):
            result = main()
            assert result == 1

    def test_main_batch_mode(self, tmp_path):
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        with (
            patch("sys.argv", ["qwen-cli", "-i", str(in_dir), "-o", str(tmp_path / "out"), "--headless"]),
            patch("modules.cli.src.surface_cli_run_command.handle", return_value={"success": True, "message": "ok"}),
        ):
            result = main()
            assert result == 0

    def test_main_watcher_mode(self, tmp_path):
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        with (
            patch("sys.argv", ["qwen-cli", "-i", str(in_dir), "-o", str(tmp_path / "out"), "--headless", "--watch"]),
            patch("modules.cli.src.surface_cli_run_command.handle", return_value={"success": True, "message": "ok"}),
        ):
            result = main()
            assert result == 0

    def test_main_auth_error(self, tmp_path):
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        with (
            patch("sys.argv", ["qwen-cli", "-i", str(in_dir), "-o", str(tmp_path / "out"), "--headless"]),
            patch(
                "modules.cli.src.surface_cli_run_command.handle",
                return_value={"success": False, "error": "AuthRequiredError: login"},
            ),
        ):
            result = main()
            assert result == 1

    def test_main_general_error(self, tmp_path):
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        with (
            patch("sys.argv", ["qwen-cli", "-i", str(in_dir), "-o", str(tmp_path / "out"), "--headless"]),
            patch("modules.root_cli_main_entry._default_container", side_effect=RuntimeError("boom")),
        ):
            result = main()
            assert result == 1
