"""CLI surface: login command — manual browser login / session setup.

Smart surface: TTY check + delegate to the CLI aggregate.
"""

from __future__ import annotations

import sys

from modules.shared.src.contract_cli_aggregate import ICliAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig


def handle(_args: object, cli: ICliAggregate, cfg: AppConfig) -> dict[str, object]:
    """Run manual login in a visible browser window."""
    if not sys.stdin.isatty():
        return {
            "success": False,
            "error": "Manual login requires an interactive terminal (TTY).",
            "category": "validation_error",
            "ref": "cli-400",
        }
    try:
        cli.run_manual_login(cfg)
        return {"success": True, "message": "Login session saved."}
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "category": "unexpected",
            "ref": "cli-500",
        }
