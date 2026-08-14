"""Error mapping utilities.

Utility layer (utility_core_error_mapping): convert exceptions to ResponseText.
Stateless function consumed by Agent orchestrator for error handling.
"""

from __future__ import annotations

from modules.shared.src.taxonomy_core_vo import ResponseText


# Error type to category mapping for structured error codes
_ERROR_CATEGORIES: dict[str, str] = {
    "AuthRequiredError": "AUTH_REQUIRED",
    "ResponseTimeoutError": "RESPONSE_TIMEOUT",
    "UploadVerificationError": "UPLOAD_FAILED",
    "PromptInjectionVerificationError": "INJECTION_FAILED",
    "UploadTimeoutError": "UPLOAD_TIMEOUT",
    "UIInteractionError": "UI_INTERACTION_FAILED",
    "BrowserLaunchError": "BROWSER_LAUNCH_FAILED",
    "CircuitBreakerOpenError": "CIRCUIT_BREAKER_OPEN",
    "QuarantineError": "QUARANTINED",
    "SendDispatchError": "DISPATCH_FAILED",
    "OutputValidationError": "OUTPUT_VALIDATION_FAILED",
    "FileValidationError": "FILE_VALIDATION_FAILED",
}


def to_error_response(exc: BaseException) -> ResponseText:
    """Map an exception into a structured ResponseText error string.

    Uses type-based categorization for common error types to provide
    meaningful error codes in CLI output.

    Parameters
    ----------
    exc : BaseException
        The exception to convert.

    Returns
    -------
    ResponseText
        Formatted error response string.

    """
    exc_type = type(exc).__name__
    category = _ERROR_CATEGORIES.get(exc_type, exc_type.upper())
    return ResponseText(f"ERROR [{category}]: {exc}")
