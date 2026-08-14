"""CLI surface: interactive controller — TUI menu, headless prompt, file picker.

Smart surface: presentation and TTY interaction only; all back-end work is
delegated to the shared core aggregate.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from modules.cli.src.surface_cli_session_setup import run_session_setup
from modules.core.src.utility_core_config_factory import build_app_config
from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_OUTPUT,
    DEFAULT_TODO,
)
from modules.shared.src.utility_core_path import list_input_files
from modules.shared.src.utility_core_response import error_response, safe_handle, success_response


def _base_config(mode: str, headless: bool = False) -> AppConfig:
    """Build an AppConfig with default XDG paths."""
    return build_app_config(mode=mode, headless=headless)


class InteractiveController:
    """Interactive TUI controller — presentation only, delegates to the aggregate."""

    def __init__(self, core: ICoreAggregate) -> None:
        """Inject the core aggregate."""
        self._core = core

    def interactive_prompt(self) -> AppConfig | None:
        """Display interactive TUI menu and build AppConfig from user selections."""
        if not sys.stdin.isatty():
            print("[ERROR] Interactive mode requires a TTY. Please provide CLI arguments.", file=sys.stderr)
            return None

        print("\n╭─ qwen-cli interactive setup ───────────────────╮")
        print("│ 1. Watcher Mode                                  │")
        print("│ 2. Batch Mode                                    │")
        print("│ 3. Single File Mode                              │")
        print("│ 4. Session Setup                                 │")
        print("│ 5. Initialize Workspace                          │")
        print("│ 6. Exit                                          │")
        print("╰──────────────────────────────────────────────────╯")

        choice = input("Select [1-6, default=1]: ").strip() or "1"
        if choice == "6":
            print("Goodbye!")
            return None

        if choice == "5":
            self._core.init_workspace(Path.cwd())
            return None

        if choice == "4":
            return _base_config("login", headless=False)

        headless = input("Run headless? [y/N, default=N]: ").strip().lower() == "y"
        mode_map: dict[str, Literal["watcher", "batch", "single", "login"]] = {
            "1": "watcher",
            "2": "batch",
            "3": "single",
        }
        mode: Literal["watcher", "batch", "single", "login"] = mode_map.get(choice, "watcher")

        if mode == "single":
            available_files = list_input_files(DEFAULT_TODO)
            if available_files:
                print("\n[FILES] Available input files:")
                for idx, (_abs_p, rel_p) in enumerate(available_files, 1):
                    print(f"  {idx}. {rel_p}")

                file_choice = input(f"Select input file [1-{len(available_files)}, default=1]: ").strip() or "1"
                try:
                    choice_idx = int(file_choice) - 1
                    if 0 <= choice_idx < len(available_files):
                        chosen_abs, _chosen_rel = available_files[choice_idx]
                    else:
                        chosen_abs, _chosen_rel = available_files[0]
                except ValueError:
                    chosen_abs, _chosen_rel = available_files[0]

                return build_app_config(mode=mode, input_path=chosen_abs, output_path=DEFAULT_OUTPUT, headless=headless)
            else:
                input_file = input(f"Enter input file path [default: {DEFAULT_TODO}]: ").strip() or str(DEFAULT_TODO)
                output_file = input(f"Enter output file path [default: {DEFAULT_OUTPUT}]: ").strip() or str(
                    DEFAULT_OUTPUT
                )
                return build_app_config(
                    mode=mode, input_path=Path(input_file), output_path=Path(output_file), headless=headless
                )

        return _base_config(mode, headless=headless)

    @safe_handle
    def run(self, cfg: AppConfig | None = None, *, prompt: bool = True) -> dict[str, object]:
        """Present the TUI menu and execute the selected mode.

        ``main`` supplies a previously selected configuration with
        ``prompt=False`` so the interactive selection has exactly one owner.
        The optional arguments preserve the controller's original public API
        for callers that want menu selection and execution in one call.
        """
        if prompt and not sys.stdin.isatty():
            return error_response(
                RuntimeError("Interactive mode requires a TTY. Please provide CLI arguments."),
                "validation_error",
                "cli-400",
            )

        selected = self.interactive_prompt() if prompt else cfg
        if selected is None:
            return success_response("Exited.")
        if selected.mode == "login":
            valid, status = self._core.validate_session(session_path=selected.session_path)

            def _do_login() -> None:
                self._core.delete_session(session_path=selected.session_path)
                result = self._core.setup_session(
                    wait_for_confirmation=None,
                    session_path=selected.session_path,
                )
                print(result)

            def _do_back() -> None:
                print("Kembali ke menu utama.")

            run_session_setup(status, on_login=_do_login, on_back=_do_back)
            return success_response("Kembali ke menu utama.")

        result = self._core.process_mode(selected)
        return success_response(result)
