"""Taxonomy definitions for qwen-web domain errors and error categories."""

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
    """Raised when response content fails sanity check, such as a challenge page."""


class FileUploadError(QwenCliError):
    """Base exception for file upload errors."""


class FileValidationError(FileUploadError):
    """Raised when file pre-flight validation fails."""


class UploadTimeoutError(FileUploadError):
    """Raised when Playwright interactions encounter an upload timeout."""


class UIInteractionError(FileUploadError):
    """Raised when upload UI elements cannot be found or interacted with."""


class PipelineError(QwenCliError):
    """Base exception for queue processing pipeline errors."""


class QuarantineError(PipelineError):
    """Raised when a file fails all processing attempts and is moved to quarantine."""


class SendDispatchError(QwenCliError):
    """Raised when all send strategies fail."""


class OutputWriteError(QwenCliError):
    """Raised when writing output or metadata sidecar fails."""


class ResponseTimeoutError(QwenCliError):
    """Raised when the AI response detection times out after dispatch."""

    def __init__(self, message: str = "Response detection timed out", timeout_sec: int = 0) -> None:
        super().__init__(message)
        self.timeout_sec = timeout_sec


class UploadVerificationError(QwenCliError):
    """Raised when upload verification fails - file was not confirmed as uploaded."""


class PromptInjectionVerificationError(QwenCliError):
    """Raised when prompt injection verification fails - text not confirmed in input."""


_ERROR_CATEGORY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("auth", "login", "captcha", "signin"), "auth"),
    (("network", "connection", "dns", "socket"), "network"),
    (("rate", "limit", "throttl", "429"), "rate_limit"),
    (("browser", "launch", "dom", "playwright", "chromium"), "browser"),
    (("injection", "paste", "clipboard", "fill"), "injection"),
    # Response timeout - specific phrases that indicate response/stream issues
    (("no response detected", "response timeout", "timeout after"), "response_timeout"),
    (("stream", "thinking", "generation"), "response_timeout"),
    (("upload", "file_upload", "attachment"), "upload"),
    (("parse", "empty"), "parsing"),
    (("file", "ioerror", "disk", "read", "write"), "file_io"),
)


class ErrorCategory:
    """Categorize errors for dashboards and alerting."""

    @staticmethod
    def categorize(exc: BaseException) -> str:
        """Return the error category string."""
        exc_type = type(exc).__name__.lower()
        msg = str(exc).lower()
        for keywords, category in _ERROR_CATEGORY_RULES:
            if any(keyword in msg or keyword in exc_type for keyword in keywords):
                return category
        if isinstance(exc, (OSError, IOError)):
            return "file_io"
        return "other"


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
    "OutputValidationError",
    "FileUploadError",
    "FileValidationError",
    "UploadTimeoutError",
    "UIInteractionError",
    "PipelineError",
    "QuarantineError",
    "SendDispatchError",
    "OutputWriteError",
    "ResponseTimeoutError",
    "UploadVerificationError",
    "PromptInjectionVerificationError",
    "ErrorCategory",
]
