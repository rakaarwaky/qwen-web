"""CLI surface: login command — manual browser login / session setup.

Smart surface: TTY check + interactive ENTER prompt; delegates the browser
session to the shared core aggregate.
"""

from __future__ import annotations

import sys

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig


def handle(_args: object, core: ICoreAggregate, cfg: AppConfig) -> dict[str, object]:
    """Run manual login in a visible browser window."""
    if not sys.stdin.isatty():
        return {
            "success": False,
            "error": "Manual login requires an interactive terminal (TTY).",
            "category": "validation_error",
            "ref": "cli-400",
        }
    try:
        print("Please log in or resolve CAPTCHA in the browser window.")
        core.setup_session()
        print("Press [ENTER] once you have finished logging in:")
        input()
        return {"success": True, "message": "Login session saved."}
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "category": "unexpected",
            "ref": "cli-500",
        }
