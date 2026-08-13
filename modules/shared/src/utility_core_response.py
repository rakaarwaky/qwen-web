"""Response envelope utilities for surface commands.

Utility layer (utility_core_response): stateless functions for building
standardized success/error response dicts used by CLI/MCP surfaces.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable


def safe_handle(
    fn: Callable[..., dict[str, object]],
) -> Callable[..., dict[str, object]]:
    """Wrap a surface handler with try/except → success/error envelope.

    Eliminates the duplicated try/except skeleton across CLI and MCP surfaces.

    Parameters
    ----------
    fn : Callable
        Handler function that returns a response dict on success.

    Returns
    -------
    Callable
        Wrapped handler that catches all exceptions and returns an error envelope.

    Example
    -------
    >>> @safe_handle
    ... def handle(args, core):
    ...     core.init_workspace(Path.cwd())
    ...     return {"success": True, "message": "done"}
    """

    @wraps(fn)
    def wrapper(*args: object, **kwargs: object) -> dict[str, object]:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            return error_response(exc)

    return wrapper


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
