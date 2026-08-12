"""Domain errors for qwen-web.

Taxonomy layer (taxonomy(error)): 18 domain exceptions, VO fields only.
"""

from __future__ import annotations


class QwenCliError(RuntimeError):
    """Base exception for qwen-cli errors."""


class AuthRequiredError(QwenCliError):
    """Raised when authentication challenge/login is required in headless mode."""


class PromptInjectionError(QwenCliError):
    """Raised when prompt text injection into Qwen input fails across all strategies."""


class RateLimitError(QwenCliError):
    """Raised when the server returns a rate-limit / throttling response."""


class CircuitBreakerOpenError(QwenCliError):
    """Raised when the circuit breaker trips due to consecutive failures."""


class BrowserLaunchError(QwenCliError):
    """Raised when the browser context cannot be launched."""


class SingleInstanceError(RuntimeError):
    """Raised when another instance of qwen-cli is already running."""


class ElementNotFoundError(QwenCliError):
    """Raised when a required DOM element is not found on the page."""


class NetworkTimeoutError(QwenCliError):
    """Raised when network operation times out or drops."""


class OutputValidationError(QwenCliError):
    """Raised when response content fails sanity check (e.g. captcha/error page)."""


class FileUploadError(QwenCliError):
    """Base exception for file upload errors."""


class FileValidationError(FileUploadError):
    """Raised when file pre-flight validation fails."""


class UploadTimeoutError(FileUploadError):
    """Raised when Playwright interactions encounter a timeout during upload."""


class UIInteractionError(FileUploadError):
    """Raised when upload UI elements cannot be found or interacted with."""


class PipelineError(QwenCliError):
    """Base exception for queue processing pipeline errors."""


class QuarantineError(PipelineError):
    """Raised when a file fails all processing attempts and is moved to quarantine."""


class SendDispatchError(QwenCliError):
    """Raised when clicking the send button or triggering send key fails across all strategies."""


class OutputWriteError(QwenCliError):
    """Raised when writing output or metadata sidecar file fails."""
