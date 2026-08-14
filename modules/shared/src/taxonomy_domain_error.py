"""Backward-compatible facade for the canonical domain error taxonomy.

New code should import from ``taxonomy_core_error``. This module remains to
avoid breaking downstream integrations that used the pre-refactor path.
"""

from __future__ import annotations

from . import taxonomy_core_error as _canonical_errors
from .taxonomy_core_vo import EventDetails

__all__ = [
    "QwenCliError",
    "AuthRequiredError",
    "PromptInjectionError",
    "RateLimitError",
    "CircuitBreakerOpenError",
    "BrowserLaunchError",
    "SingleInstanceError",
    "ElementNotFoundError",
    "NetworkTimeoutError",
    "ResponseDetectionTimeoutError",
    "OutputValidationError",
    "FileUploadError",
    "FileValidationError",
    "UploadFailureError",
    "UploadTimeoutError",
    "UIInteractionError",
    "PipelineError",
    "QuarantineError",
    "SendDispatchError",
    "OutputWriteError",
    "ErrorCategory",
    "EventDetails",
]


def __getattr__(name: str) -> object:
    """Resolve legacy errors from the canonical taxonomy module."""
    if name == "EventDetails":
        return EventDetails
    if name in _canonical_errors.__all__:
        return getattr(_canonical_errors, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
