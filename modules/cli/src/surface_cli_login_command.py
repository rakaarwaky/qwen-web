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
    """Run manual login in a visible browser window."""
    if not sys.stdin.isatty():
        return error_response(
            RuntimeError("Manual login requires an interactive terminal (TTY)."), "validation_error", "cli-400"
        )
    print("Please log in or resolve CAPTCHA in the browser window.")
    core.setup_session()
    print("Press [ENTER] once you have finished logging in:")
    input()
    return success_response(f"Login session saved to '{cfg.session_path}'.")
