"""Contract: external adapter protocols (AES402: ABCs with VO signatures)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class IBrowserProtocol(ABC):
    """Protocol for browser lifecycle management (Playwright adapter)."""

    @abstractmethod
    def is_alive(self) -> bool:
        """Return True if the browser session and Qwen chat UI are responsive."""
        ...

    @abstractmethod
    def check_auth(self) -> None:
        """Raise AuthRequiredError if authentication is needed."""
        ...

    @abstractmethod
    def navigate_to_chat(self) -> None:
        """Navigate to chat.qwen.ai and verify session."""
        ...


class IInjectionProtocol(ABC):
    """Protocol for prompt text injection into Qwen input."""

    @abstractmethod
    def find_input(self) -> Any:
        """Find the input element on the Qwen Web UI."""
        ...

    @abstractmethod
    def inject_text(self, text: str) -> None:
        """Inject text into the input element."""
        ...


class ISendProtocol(ABC):
    """Protocol for sending prompts via the send button."""

    @abstractmethod
    def click_send(self) -> None:
        """Click the send button or trigger send via keyboard."""
        ...

    @abstractmethod
    def count_messages(self) -> int:
        """Count the number of chat messages."""
        ...

    @abstractmethod
    def latest_message_text(self) -> str | None:
        """Get the latest assistant message text."""
        ...


class IStreamProtocol(ABC):
    """Protocol for waiting on AI response streaming."""

    @abstractmethod
    def wait_for_response(
        self,
        timeout_sec: int,
        msg_count_before: int,
    ) -> str | None:
        """Wait for AI response with stability checks and validation."""
        ...

    @abstractmethod
    def is_generation_complete(self) -> bool:
        """Check if generation is complete."""
        ...

    @abstractmethod
    def is_thinking_active(self) -> bool:
        """Check if AI thinking indicator is active."""
        ...


class IUploadProtocol(ABC):
    """Protocol for file attachment upload."""

    @abstractmethod
    def upload_attachment(
        self,
        filepath: Path,
    ) -> bool:
        """Upload a file as an attachment to the current chat."""
        ...


class ISaverProtocol(ABC):
    """Protocol for output file writing with metadata."""

    @abstractmethod
    def write_output(
        self,
        path: Path,
        content: str,
        run_id: str,
        src: str,
        dur: float,
        input_chars: int,
        output_chars: int,
    ) -> None:
        """Write processed output to disk with metadata traceability header."""
        ...


class IObservabilityProtocol(ABC):
    """Protocol for observability setup and status writing."""

    @abstractmethod
    def setup_observability(self, log_path: Path) -> None:
        """Bootstrap observability stack: Sentry → OTel → structlog → hooks."""
        ...

    @abstractmethod
    def write_status(
        self,
        status: str,
        mode: str,
        headless: bool,
        run_id: str | None,
    ) -> None:
        """Write status to JSON status file for systemd/monitoring."""
        ...


class IFileSystemProtocol(ABC):
    """Protocol for filesystem operations."""

    @abstractmethod
    def log_step(
        self,
        run_id: str,
        step: str,
        src: str,
        status: str,
        details: dict[str, Any] | None,
    ) -> None:
        """Log a granular step-by-step event execution."""
        ...


class IAuditRepository(ABC):
    """Protocol for audit trail persistence."""

    @abstractmethod
    def log(
        self,
        status: str,
        run_id: str,
        src: str,
        dst: str,
        dur: float,
        in_c: int,
        out_c: int,
        err: str,
    ) -> None:
        """Log a completed file processing result."""
        ...

    @abstractmethod
    def log_step(
        self,
        run_id: str,
        step: str,
        src: str,
        status: str,
        details: dict[str, Any] | None,
    ) -> None:
        """Log a pipeline step."""