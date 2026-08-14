"""Backward-compatible facade for the canonical domain error taxonomy.

New code should import from ``taxonomy_core_error``. This module remains to
avoid breaking downstream integrations that used the pre-refactor path.
"""

from __future__ import annotations

from .taxonomy_core_error import (
    AuthRequiredError,
    BrowserLaunchError,
    CircuitBreakerOpenError,
    ElementNotFoundError,
    ErrorCategory,
    FileUploadError,
    FileValidationError,
    NetworkTimeoutError,
    OutputValidationError,
    OutputWriteError,
    PipelineError,
    PromptInjectionError,
    QuarantineError,
    QwenCliError,
    RateLimitError,
    ResponseDetectionTimeoutError,
    SendDispatchError,
    SingleInstanceError,
    UIInteractionError,
    UploadFailureError,
    UploadTimeoutError,
)
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
