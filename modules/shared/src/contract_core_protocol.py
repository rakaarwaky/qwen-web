"""Core capability protocols (contract layer).

Taxonomy layer (contract(protocol)): pure ABCs, signatures use VOs where possible.
Capabilities implement these; agents/surfaces depend on them via DI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from playwright.sync_api import BrowserContext, ElementHandle, Page

from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.taxonomy_core_event import LifecycleEmitter
from modules.shared.src.taxonomy_core_vo import RunContext


class IUploadProtocol(ABC):
    """File upload capability contract (external Qwen Web UI adaptation)."""

    @abstractmethod
    def upload_attachment(
        self,
        page: Page,
        filepath: Path,
        config: Any | None = None,
        emitter: LifecycleEmitter | None = None,
        web_loaded: bool = True,
    ) -> bool:
        """Attach a file as an attachment. Returns True on success."""

    @abstractmethod
    def validate_file(self, filepath: Path, max_size_mb: float = 100.0) -> int:
        """Pre-flight validation; returns file size in bytes."""


class IInjectionProtocol(ABC):
    """Prompt text injection capability contract."""

    @abstractmethod
    def find_input(self, page: Page, config: Any | None = None) -> ElementHandle:
        """Locate the input element; raise if not found."""

    @abstractmethod
    def inject_text(self, page: Page, text: str, config: Any | None = None) -> None:
        """Inject prompt text via multi-strategy DOM injection."""


class ISendProtocol(ABC):
    """Send dispatcher capability contract."""

    @abstractmethod
    def click_send(
        self,
        page: Page,
        emitter: LifecycleEmitter,
        config: Any | None = None,
        document_parsed: bool = True,
    ) -> None:
        """Trigger the send action."""

    @abstractmethod
    def count_messages(self, page: Page) -> int:
        """Count chat turns."""

    @abstractmethod
    def latest_message_text(self, page: Page) -> str | None:
        """Return the latest assistant response text."""


class IStreamProtocol(ABC):
    """Response streaming capability contract."""

    @abstractmethod
    def wait_for_response(
        self,
        page: Page,
        timeout_sec: int,
        msg_count_before: int,
        emitter: LifecycleEmitter,
        polling_interval_sec: float = 1.0,
        stability_checks: int = 4,
        min_text_length: int = 1,
        dispatch_acknowledged: bool = True,
    ) -> str | None:
        """Wait for a stable assistant response; return its text."""

    @abstractmethod
    def is_generation_complete(self, page: Page) -> bool:
        """True when Qwen has finished generating."""

    @abstractmethod
    def is_thinking_active(self, page: Page) -> bool:
        """True when Qwen is currently thinking/streaming."""


class IBrowserProtocol(ABC):
    """Browser lifecycle capability contract (Playwright adaptation)."""

    @abstractmethod
    def browser_session(self, cfg: Any) -> Any:
        """Context manager yielding a BrowserContext."""

    @abstractmethod
    def navigate_to_chat(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Navigate to chat and verify auth."""

    @abstractmethod
    def check_auth(self, page: Page) -> None:
        """Raise AuthRequiredError if not authenticated."""

    @abstractmethod
    def reset_page(self, page: Page, emitter: LifecycleEmitter) -> None:
        """Reset the page to a clean chat state."""


class ISaverProtocol(ABC):
    """Output persistence capability contract."""

    @abstractmethod
    def write_output(
        self,
        path: Path,
        content: str,
        ctx: RunContext,
        src: str,
        dur: float,
        input_chars: int,
        output_chars: int,
        config: Any | None = None,
    ) -> None:
        """Write processed output with metadata header + sidecar."""


class IObservabilityProtocol(ABC):
    """Observability capability contract (logging, tracing, hooks)."""

    @abstractmethod
    def setup_observability(self, log_path: Path) -> None:
        """Bootstrap Sentry/OTel/structlog + global hooks."""

    @abstractmethod
    def get_logger(self, name: str = "qwen-cli") -> Any:
        """Return a bound logger."""

    @abstractmethod
    def start_span(self, name: str) -> Any:
        """Return a span context manager (or no-op)."""

    @abstractmethod
    def bind_run_context(self, run_id: str, **extra: Any) -> None:
        """Bind run-scoped contextvars."""

    @abstractmethod
    def clear_run_context(self) -> None:
        """Clear run-scoped contextvars."""

    @abstractmethod
    def exit_code_for(self, exc: BaseException) -> int:
        """Map an unhandled exception to a process exit code."""

    @abstractmethod
    def install_excepthooks(self) -> None:
        """Install global exception handlers."""


class IFileSystemProtocol(ABC):
    """Audit log persistence contract (I/O over the filesystem)."""

    @abstractmethod
    def log_step(
        self,
        ctx: RunContext,
        step: str,
        src: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log a granular step event."""

    @abstractmethod
    def log(
        self,
        status: str,
        ctx: RunContext,
        src: str,
        dst: str,
        dur: float,
        in_c: int,
        out_c: int,
        err: str = "",
    ) -> None:
        """Log a completed file processing result."""


class ILinuxProtocol(ABC):
    """Linux-native single-instance lock and sd_notify contract."""

    @abstractmethod
    def acquire_lock(self) -> Any:
        """Acquire the single-instance file lock; raise SingleInstanceError if held."""

    @abstractmethod
    def release_lock(self, lock: Any) -> None:
        """Release a previously acquired lock."""

    @abstractmethod
    def sd_notify_ready(self) -> None:
        """Notify systemd that the app is ready."""

    @abstractmethod
    def sd_notify_stop(self) -> None:
        """Notify systemd that the app is stopping."""


__all__ = [
    "IUploadProtocol",
    "IInjectionProtocol",
    "ISendProtocol",
    "IStreamProtocol",
    "IBrowserProtocol",
    "ISaverProtocol",
    "IObservabilityProtocol",
    "IFileSystemProtocol",
    "ILinuxProtocol",
    "BrowserContext",
    "CircuitBreaker",
    "RateLimiter",
]
