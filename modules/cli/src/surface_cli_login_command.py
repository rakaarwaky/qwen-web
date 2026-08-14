"""CLI surface for manual login/session setup."""

from __future__ import annotations

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.utility_core_response import safe_handle, success_response


@safe_handle
def handle(_args: object, core: ICoreAggregate, cfg: AppConfig) -> dict[str, object]:
    """Validate or establish a manual login session in a visible browser.

    The user logs in manually in the headed browser, then closes it — that
    triggers the session check. No ENTER press needed.
    """
    core.delete_session(session_path=cfg.session_path)

    result = core.setup_session(
        wait_for_confirmation=None,
        session_path=cfg.session_path,
    )
    return success_response(result)
