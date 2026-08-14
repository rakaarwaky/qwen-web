"""CLI surface: run command — watcher/batch/single processing dispatch.

Smart surface: maps parsed args to a config VO, delegates to the core aggregate.
"""

from __future__ import annotations

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_core_vo import AppConfig
from modules.shared.src.utility_core_response import error_response, safe_handle, success_response


@safe_handle
def handle(args: object, core: ICoreAggregate) -> dict[str, object]:
    """Dispatch processing based on AppConfig.mode."""
    cfg: AppConfig | None = getattr(args, "_cfg", None)
    if cfg is None:
        return error_response(
            RuntimeError("Missing AppConfig — run command requires a built config."), "validation_error", "cli-400"
        )

    result = core.process_mode(cfg)
    return success_response(result)
