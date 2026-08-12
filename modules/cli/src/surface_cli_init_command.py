"""CLI surface: init command — initialize workspace (.agents/skills + .qwen-web).

Smart surface: delegates to the CLI aggregate, zero business logic.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.contract_cli_aggregate import ICliAggregate


def handle(args: object, cli: ICliAggregate) -> dict[str, object]:
    """Initialize the workspace in the target directory."""
    target_dir = getattr(args, "target_dir", None) or Path.cwd()
    try:
        cli.init_workspace(target_dir)
        return {"success": True, "message": f"Workspace initialized in {target_dir}"}
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "category": "unexpected",
            "ref": "cli-500",
        }
