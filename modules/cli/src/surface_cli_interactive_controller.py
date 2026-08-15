"""CLI surface: interactive controller — TUI menu, headless prompt, file picker.

Smart surface: presentation and TTY interaction only; all back-end work is
delegated to the shared core aggregate.
"""

from __future__ import annotations

import sys
from pathlib import Path

from modules.cli.src.surface_cli_session_setup import run_session_setup
from modules.core.src.utility_core_config_factory import build_app_config
from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig
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
        print("│ 1. Run Prompt (Single Mode)                      │")
        print("│ 2. Session Setup (Login)                         │")
        print("│ 3. Initialize Workspace                          │")
        print("│ 4. Exit                                          │")
        print("╰──────────────────────────────────────────────────╯")

        choice = input("Select [1-4, default=1]: ").strip() or "1"
        if choice == "4":
            print("Goodbye!")
            return None

        if choice == "3":
            self._core.init_workspace(Path.cwd())
            return None

        if choice == "2":
            return _base_config("login", headless=False)

        headless = input("Run headless? [y/N, default=N]: ").strip().lower() == "y"
        prompt_file = input("Enter prompt file path: ").strip()
        if not prompt_file:
            print("[ERROR] Prompt file is required.", file=sys.stderr)
            return None

        p_path = Path(prompt_file).resolve()
        if not p_path.exists():
            print(f"[ERROR] File not found: {prompt_file}", file=sys.stderr)
            return None

        file_upload = input("Enter optional attachment file path [skip]: ").strip()
        f_path = Path(file_upload).resolve() if file_upload else None

        output_file = input("Enter output path [default: output folder]: ").strip()
        out_path = Path(output_file).resolve() if output_file else None

        return build_app_config(
            mode="single",
            input_path=p_path,
            output_path=out_path,
            prompt_file=p_path,
            prompt_path=p_path,
            file_path=f_path,
            headless=headless,
        )

    @safe_handle
    def run(self, cfg: AppConfig | None = None, *, prompt: bool = True) -> dict[str, object]:
        """Present the Textual Obsidian Nebula TUI and execute interactions."""
        if prompt and not sys.stdin.isatty():
            return error_response(
                RuntimeError("Interactive mode requires a TTY. Please provide CLI arguments."),
                "validation_error",
                "cli-400",
            )

        if prompt:
            from modules.cli.src.surface_cli_tui_app import QwenTuiApp

            app = QwenTuiApp(self._core)
            app.run()
            return success_response("TUI Session Closed.")

        if cfg is None:
            return success_response("Exited.")

        result = self._core.process_mode(cfg)
        return success_response(result)
