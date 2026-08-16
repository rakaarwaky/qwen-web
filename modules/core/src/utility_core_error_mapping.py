"""Error mapping utilities.

Utility layer (utility_core_error_mapping): convert exceptions to ResponseText.
Stateless function consumed by Agent orchestrator for error handling.
"""

from __future__ import annotations

from modules.shared.src.taxonomy_core_vo import ResponseText


def to_error_response(exc: BaseException) -> ResponseText:
    """Map an exception into a structured ResponseText error string."""
    code = "AUTH_REQUIRED" if type(exc).__name__ == "AuthRequiredError" else type(exc).__name__
    return ResponseText(f"ERROR [{code}]: {exc}")
