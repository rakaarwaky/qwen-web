"""Error mapping utilities.

Utility layer (utility_core_error_mapping): convert exceptions to ResponseText.
Stateless function consumed by Agent orchestrator for error handling.
"""

from __future__ import annotations

from modules.shared.src.taxonomy_core_vo import ResponseText


def to_error_response(exc: BaseException) -> ResponseText:
    """Map an exception into a structured ResponseText error string.

    AuthRequiredError maps to ERROR [AUTH_REQUIRED]: <message>.
    All other exceptions map to ERROR [<ClassName>]: <message>.

    Parameters
    ----------
    exc : BaseException
        The exception to convert.

    Returns
    -------
    ResponseText
        Formatted error response string.

    """
    if type(exc).__name__ == "AuthRequiredError":
        return ResponseText(f"ERROR [AUTH_REQUIRED]: {exc}")
    return ResponseText(f"ERROR [{type(exc).__name__}]: {exc}")
