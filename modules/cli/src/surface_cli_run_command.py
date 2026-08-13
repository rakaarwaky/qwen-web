"""CLI surface: run command — watcher/batch/single processing dispatch.

Smart surface: maps parsed args to a config VO, delegates to the core aggregate.
"""

from __future__ import annotations

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_vo import HeadlessFlag, TimeoutSec
from modules.shared.src.utility_core_response import error_response, success_response


def handle(args: object, core: ICoreAggregate) -> dict[str, object]:
    """Dispatch watcher/batch/single processing based on parsed CLI args."""
    cfg: AppConfig | None = getattr(args, "_cfg", None)
    if cfg is None:
        return error_response(RuntimeError("Missing AppConfig — run command requires a built config."), "validation_error", "cli-400")

    try:
        if cfg.mode == "watcher":
            result = core.process_watcher(TimeoutSec(cfg.interval), HeadlessFlag(cfg.headless))
        elif cfg.mode == "single":
            result = core.process_single_file(cfg.input_path, cfg.output_path, HeadlessFlag(cfg.headless))
        else:
            result = core.process_batch(cfg.input_path, cfg.output_path, HeadlessFlag(cfg.headless))
        return success_response(result)
    except Exception as e:
        return error_response(e)
