"""CLI surface: run command — watcher/batch/single processing dispatch.

Smart surface: maps parsed args to a config VO, delegates to the core aggregate.
"""

from __future__ import annotations

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_vo import HeadlessFlag, TimeoutSec


def handle(args: object, core: ICoreAggregate) -> dict[str, object]:
    """Dispatch watcher/batch/single processing based on parsed CLI args."""
    cfg: AppConfig | None = getattr(args, "_cfg", None)
    if cfg is None:
        return {
            "success": False,
            "error": "Missing AppConfig — run command requires a built config.",
            "category": "validation_error",
            "ref": "cli-400",
        }

    try:
        if cfg.mode == "watcher":
            result = core.process_watcher(TimeoutSec(cfg.interval), HeadlessFlag(cfg.headless))
        elif cfg.mode == "single":
            result = core.process_single_file(cfg.input_path, cfg.output_path, HeadlessFlag(cfg.headless))
        else:
            result = core.process_batch(cfg.input_path, cfg.output_path, HeadlessFlag(cfg.headless))
        return {"success": True, "message": result}
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "category": "unexpected",
            "ref": "cli-500",
        }
