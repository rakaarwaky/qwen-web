"""CLI surface: interactive controller — TUI menu, headless prompt, file picker.

Smart surface: presentation only; delegates to the CLI aggregate for the menu,
then hands the resulting AppConfig to the run command.
"""

from __future__ import annotations

from modules.shared.src.contract_cli_aggregate import ICliAggregate
from modules.shared.src.contract_core_aggregate import ICoreAggregate


class InteractiveController:
    """Interactive TUI controller — presentation only, delegates to aggregates."""

    def __init__(self, cli: ICliAggregate, core: ICoreAggregate) -> None:
        """Inject the CLI and core aggregates."""
        self._cli = cli
        self._core = core

    def run(self) -> dict[str, object]:
        """Present the TUI menu and execute the selected mode."""
        cfg = self._cli.interactive_prompt()
        if cfg is None:
            return {"success": True, "message": "Exited."}
        if cfg.mode == "login":
            self._cli.run_manual_login(cfg)
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
