"""Core qwen-web domain value objects: brand (NewType) types, run context,
lifecycle events, and the pipeline event enum.

Taxonomy layer (taxonomy(vo)): frozen dataclasses, enums, and brand aliases — no I/O.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, NewType

PromptText = NewType("PromptText", str)
InputPath = NewType("InputPath", str)
OutputPath = NewType("OutputPath", str)
FilePath = NewType("FilePath", str)
RunId = NewType("RunId", str)
RunIdHex = NewType("RunIdHex", str)
RunContextId = NewType("RunContextId", str)
MessageCount = NewType("MessageCount", int)
ResponseText = NewType("ResponseText", str)
StabilityCount = NewType("StabilityCount", int)
TimeoutSec = NewType("TimeoutSec", int)
PollIntervalSec = NewType("PollIntervalSec", float)
HeadlessFlag = NewType("HeadlessFlag", bool)
Mode = NewType("Mode", str)

# ─── Brand types: timing & limits ─────────────────────────────
TypingDelayMs = NewType("TypingDelayMs", int)
WaitTimeoutMs = NewType("WaitTimeoutMs", int)
ClickTimeoutMs = NewType("ClickTimeoutMs", int)
BackoffDelaySec = NewType("BackoffDelaySec", float)
MaxRetries = NewType("MaxRetries", int)
StabilityChecks = NewType("StabilityChecks", int)
MinTextLength = NewType("MinTextLength", int)

# ─── Brand types: upload config ───────────────────────────────
MaxFileSizeMb = NewType("MaxFileSizeMb", float)
DropdownTimeoutMs = NewType("DropdownTimeoutMs", int)
OptionTimeoutMs = NewType("OptionTimeoutMs", int)
FileChooserTimeoutMs = NewType("FileChooserTimeoutMs", int)
CardRenderTimeoutMs = NewType("CardRenderTimeoutMs", int)

# ─── Brand types: saver config ────────────────────────────────
InputChars = NewType("InputChars", int)
OutputChars = NewType("OutputChars", int)
IncludeHeaderFlag = NewType("IncludeHeaderFlag", bool)
GenerateSidecarFlag = NewType("GenerateSidecarFlag", bool)
AtomicWriteFlag = NewType("AtomicWriteFlag", bool)

# ─── Brand types: browser & observability config ──────────────
ChromeProfile = NewType("ChromeProfile", str)
ConfigPath = NewType("ConfigPath", str)
DisableSandboxFlag = NewType("DisableSandboxFlag", bool)
UserAgent = NewType("UserAgent", str)
ServerName = NewType("ServerName", str)
ServiceName = NewType("ServiceName", str)
Environment = NewType("Environment", str)
TryEnterKeyFallbackFlag = NewType("TryEnterKeyFallbackFlag", bool)

# ─── Brand types: circuit breaker & rate limiter config ───────
FailureThreshold = NewType("FailureThreshold", int)
WindowSec = NewType("WindowSec", int)
MaxPerMinute = NewType("MaxPerMinute", int)

# ─── Brand types: stream & file validation config ────────────
FileSizeBytes = NewType("FileSizeBytes", int)

# ─── Brand types: observability & logging config ─────────────
LoggerName = NewType("LoggerName", str)
ExitCode = NewType("ExitCode", int)


@dataclass
class RunContext:
    """Run-scoped context with auto-generated run ID.

    Attributes
    ----------
    run_id : str
        Unique identifier: YYYYMMDD_HHMMSS_randomhex[:6].

    """

    run_id: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    )


class QwenEventType(str, Enum):
    """Enterprise-level enum for Qwen Web pipeline event types (chronologically ordered)."""

    def __str__(self) -> str:
        """Return the string value of the event type."""
        return str(self.value)

    NETWORK_RECONNECTING = "EVENT_NETWORK_RECONNECTING"  # Network reconnecting
    WEB_LOADED = "EVENT_WEB_LOADED"  # Web page loaded
    DOCUMENT_PARSED = "EVENT_DOCUMENT_PARSED"  # Document parsed
    SEND_CLICKED = "EVENT_SEND_CLICKED"  # Send button clicked
    DISPATCH_ACKNOWLEDGED = "EVENT_DISPATCH_ACKNOWLEDGED"  # Dispatch acknowledged
    THINKING_STARTED = "EVENT_THINKING_STARTED"  # Qwen AI thinking
    STREAMING_GENERATION = "EVENT_STREAMING_GENERATION"  # Qwen AI typing (realtime)
    GENERATION_FINISHED = "EVENT_GENERATION_FINISHED"  # Generation finished
    OUTPUT_COPIED = "EVENT_OUTPUT_COPIED"  # Output saved


EVENT_NETWORK_RECONNECTING = QwenEventType.NETWORK_RECONNECTING
EVENT_WEB_LOADED = QwenEventType.WEB_LOADED
EVENT_DOCUMENT_PARSED = QwenEventType.DOCUMENT_PARSED
EVENT_SEND_CLICKED = QwenEventType.SEND_CLICKED
EVENT_DISPATCH_ACKNOWLEDGED = QwenEventType.DISPATCH_ACKNOWLEDGED
EVENT_THINKING_STARTED = QwenEventType.THINKING_STARTED
EVENT_STREAMING_GENERATION = QwenEventType.STREAMING_GENERATION
EVENT_GENERATION_FINISHED = QwenEventType.GENERATION_FINISHED
EVENT_OUTPUT_COPIED = QwenEventType.OUTPUT_COPIED


@dataclass
class LifecycleEvent:
    """Structured event emitted at every major lifecycle boundary."""

    name: str
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    details: dict[str, Any] = field(default_factory=dict)


LifecycleCallback = Callable[[LifecycleEvent], None]

EventDetails = dict[str, object]
EventMessage = NewType("EventMessage", str)
CallbackRegistry = dict[str, list[LifecycleCallback]]


@dataclass
class StatusRecordVO:
    """Status payload recorded for systemd/monitoring integration."""

    status: str
    mode: Mode
    headless: HeadlessFlag
    run_id: RunId | None = None
    files_processed: int = 0
    files_failed: int = 0
    cpu_sec: float | None = None
    error: str | None = None


_ERROR_CATEGORY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("auth", "login", "captcha", "signin"), "auth"),
    (("network", "connection", "timeout", "dns", "socket"), "network"),
    (("rate", "limit", "throttl", "429"), "rate_limit"),
    (("browser", "launch", "dom", "playwright", "chromium"), "browser"),
    (("injection", "paste", "clipboard", "fill"), "injection"),
    (("parse", "empty", "no response", "timeout"), "parsing"),
    (("file", "ioerror", "disk", "read", "write"), "file_io"),
)


class ErrorCategory:
    """Categorize errors for dashboards and alerting."""

    @staticmethod
    def categorize(exc: BaseException) -> str:
        """Return the error category string."""
        exc_type = type(exc).__name__.lower()
        msg = str(exc).lower()

        # Check keyword rules first (before generic OSError catches TimeoutError)
        for keywords, category in _ERROR_CATEGORY_RULES:
            if any(k in msg or k in exc_type for k in keywords):
                return category

        if isinstance(exc, (OSError, IOError)):
            return "file_io"

        return "other"


EVENT_DESCRIPTIONS: dict[QwenEventType, str] = {
    QwenEventType.NETWORK_RECONNECTING: "Reconnecting to Qwen Web...",
    QwenEventType.WEB_LOADED: "Qwen Web page loaded",
    QwenEventType.DOCUMENT_PARSED: "Document parsed",
    QwenEventType.SEND_CLICKED: "Send button clicked",
    QwenEventType.DISPATCH_ACKNOWLEDGED: "Dispatch acknowledged",
    QwenEventType.THINKING_STARTED: "Qwen AI thinking...",
    QwenEventType.STREAMING_GENERATION: "Qwen AI typing...",
    QwenEventType.GENERATION_FINISHED: "Generation finished",
    QwenEventType.OUTPUT_COPIED: "Output saved",
}
