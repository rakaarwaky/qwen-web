"""CLI surface: run command — watcher/batch/single processing dispatch.

Smart surface: maps parsed args to a config VO, delegates to the core aggregate.
"""

from __future__ import annotations

import re

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.utility_core_response import error_response, safe_handle, success_response


def _processing_failure_message(result: object) -> str | None:
    """Return a failure reason when a normal core response reports failed work."""
    message = str(result)
    if message.startswith("ERROR ["):
        return message
    match = re.search(r"\bFailed:\s*(\d+)\b", message, flags=re.IGNORECASE)
    if match and int(match.group(1)) > 0:
        return message
    return None


@safe_handle
def handle(args: object, core: ICoreAggregate) -> dict[str, object]:
    """Dispatch processing based on AppConfig.mode."""
    cfg: AppConfig | None = getattr(args, "_cfg", None)
    if cfg is None:
        return error_response(
            RuntimeError("Missing AppConfig — run command requires a built config."), "validation_error", "cli-400"
        )

    result = core.process_mode(cfg)
    failure = _processing_failure_message(result)
    if failure is not None:
        return error_response(RuntimeError(failure), "processing_failed", "cli-422")
    return success_response(result)
