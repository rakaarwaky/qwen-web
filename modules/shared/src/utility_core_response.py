"""Response envelope utilities for surface commands.

Utility layer (utility_core_response): stateless functions for building
standardized success/error response dicts used by CLI/MCP surfaces.
"""

from __future__ import annotations


def success_response(message: object) -> dict[str, object]:
    """Build a standardized success response envelope."""
    return {"success": True, "message": message}


def error_response(exc: BaseException, category: str = "unexpected", ref: str = "cli-500") -> dict[str, object]:
    """Build a standardized error response envelope.

    Parameters
    ----------
    exc : BaseException
        The exception to wrap.
    category : str
        Error category label (default: "unexpected").
    ref : str
        Human-readable reference code (default: "cli-500").

    Returns
    -------
    dict[str, object]
        {"success": False, "error": str(exc), "category": category, "ref": ref}
    """
    return {"success": False, "error": str(exc), "category": category, "ref": ref}
