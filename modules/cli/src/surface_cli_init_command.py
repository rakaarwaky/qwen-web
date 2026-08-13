"""CLI surface: init command — initialize workspace (.agents/skills + .qwen-web).

Smart surface: delegates to the shared core aggregate, zero business logic.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.utility_core_response import error_response, success_response


def handle(args: object, core: ICoreAggregate) -> dict[str, object]:
    """Initialize the workspace in the target directory."""
    target_dir = getattr(args, "target_dir", None) or Path.cwd()
    try:
        core.init_workspace(target_dir)
        return success_response(f"Workspace initialized in {target_dir}")
    except Exception as e:
        return error_response(e)
