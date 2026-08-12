"""CLI surface: interactive controller — TUI menu, headless prompt, file picker.

Smart surface: presentation and TTY interaction only; all back-end work is
delegated to the shared core aggregate.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_DONE,
    DEFAULT_FAILED,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_PROC,
    DEFAULT_SESSION,
    DEFAULT_TODO,
)
from modules.shared.src.utility_core_path import list_input_files


def _base_config(mode: str, headless: bool = False) -> AppConfig:
    """Build an AppConfig with default XDG paths."""
    return AppConfig(
        mode=mode,
        input_path=DEFAULT_TODO,
        output_path=DEFAULT_OUTPUT,
        done_path=DEFAULT_DONE,
        failed_path=DEFAULT_FAILED,
        proc_path=DEFAULT_PROC,
        session_path=DEFAULT_SESSION,
        log_path=DEFAULT_LOG,
        headless=headless,
    )


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

        print("\n╭─ qwen-cli interactive setup ─────────────────────╮")
        print("│ 1. Watcher Mode (continuous)                     │")
        print("│ 2. Batch Mode (folder)                           │")
        print("│ 3. Single File Mode                              │")
        print("│ 4. Manual Login / Session Setup                  │")
        print("│ 5. Initialize Workspace (.agents/skills & .qwen) │")
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

                return AppConfig(
                    mode=mode,
                    input_path=chosen_abs,
                    output_path=DEFAULT_OUTPUT,
                    done_path=DEFAULT_DONE,
                    failed_path=DEFAULT_FAILED,
                    proc_path=DEFAULT_PROC,
                    session_path=DEFAULT_SESSION,
                    log_path=DEFAULT_LOG,
                    headless=headless,
                )
            else:
                input_file = input(f"Enter input file path [default: {DEFAULT_TODO}]: ").strip() or str(DEFAULT_TODO)
                output_file = input(f"Enter output file path [default: {DEFAULT_OUTPUT}]: ").strip() or str(DEFAULT_OUTPUT)
                return AppConfig(
                    mode=mode,
                    input_path=Path(input_file),
                    output_path=Path(output_file),
                    done_path=DEFAULT_DONE,
                    failed_path=DEFAULT_FAILED,
                    proc_path=DEFAULT_PROC,
                    session_path=DEFAULT_SESSION,
                    log_path=DEFAULT_LOG,
                    headless=headless,
                )

        return _base_config(mode, headless=headless)

    def run(self) -> dict[str, object]:
        """Present the TUI menu and execute the selected mode."""
        cfg = self.interactive_prompt()
        if cfg is None:
            return {"success": True, "message": "Exited."}
        if cfg.mode == "login":
            self._core.setup_session()
            return {"success": True, "message": "Login session saved."}
        try:
            if cfg.mode == "watcher":
                result = self._core.process_watcher(cfg.interval, cfg.headless)
            elif cfg.mode == "single":
                result = self._core.process_single_file(cfg.input_path, cfg.output_path, cfg.headless)
            else:
                result = self._core.process_batch(cfg.input_path, cfg.output_path, cfg.headless)
            return {"success": True, "message": result}
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "category": "unexpected",
                "ref": "cli-500",
            }
