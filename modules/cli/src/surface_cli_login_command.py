"""CLI surface: login command — manual browser login / session setup.

Smart surface: TTY check + interactive ENTER prompt; delegates the browser
session to the shared core aggregate.
"""

from __future__ import annotations

import sys

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.utility_core_response import error_response, safe_handle, success_response


@safe_handle
def handle(_args: object, core: ICoreAggregate, cfg: AppConfig) -> dict[str, object]:
    """Validate or establish a manual login session in a visible browser."""
    if not sys.stdin.isatty():
        return error_response(
            RuntimeError("Manual login requires an interactive terminal (TTY)."), "validation_error", "cli-400"
        )

    def _wait_for_login() -> None:
        """Keep the headed browser alive while the user completes login."""
        print("Please log in or resolve CAPTCHA in the browser window.")
        print("Press [ENTER] here once the chat page is ready:")
        input()

    result = core.setup_session(
        wait_for_confirmation=_wait_for_login,
        session_path=cfg.session_path,
    )
    return success_response(result)
