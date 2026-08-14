"""Core qwen-web domain value objects: brand (NewType) types, run context,
Core value objects only.

Taxonomy layer (taxonomy(vo)): immutable value contracts and brand aliases — no I/O.
Lifecycle events live in taxonomy_core_event; domain errors live in taxonomy_core_error.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import NewType, TypeAlias

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
EventName: TypeAlias = str
EventTimestamp: TypeAlias = float
EventId: TypeAlias = str
EventDetails: TypeAlias = Mapping[str, object]
EventOrderMap: TypeAlias = dict[object, int]


class ProcessingStatus(str, Enum):
    """Terminal status for one queue item."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ProcessingOutcome:
    """Result of one processing attempt, including quarantine details."""

    status: ProcessingStatus
    error: str | None = None
    failed_path: Path | None = None


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


_LEGACY_EVENT_EXPORTS = (
    "QwenEventType",
    "LifecycleEvent",
    "LifecycleCallback",
    "EventDetails",
    "EventMessage",
    "CallbackRegistry",
    "EVENT_DESCRIPTIONS",
    "PIPELINE_EVENT_SEQUENCE",
    "EVENT_ORDER",
    "EVENT_NETWORK_RECONNECTING",
    "EVENT_WEB_LOADED",
    "EVENT_FILE_UPLOADED",
    "EVENT_PROMPT_INJECTED",
    "EVENT_DOCUMENT_PARSED",
    "EVENT_SEND_CLICKED",
    "EVENT_DISPATCH_ACKNOWLEDGED",
    "EVENT_THINKING_STARTED",
    "EVENT_STREAMING_GENERATION",
    "EVENT_GENERATION_FINISHED",
    "EVENT_OUTPUT_COPIED",
)

_LEGACY_ERROR_EXPORTS = (
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
    "ErrorCategory",
)


def __getattr__(name: str) -> object:
    """Resolve event and error names lazily for legacy imports."""
    if name in _LEGACY_EVENT_EXPORTS:
        from . import taxonomy_core_event

        return getattr(taxonomy_core_event, name)
    if name in _LEGACY_ERROR_EXPORTS:
        from . import taxonomy_core_error

        return getattr(taxonomy_core_error, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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


__all__ = [
    "PromptText",
    "InputPath",
    "OutputPath",
    "FilePath",
    "RunId",
    "RunIdHex",
    "RunContextId",
    "MessageCount",
    "ResponseText",
    "StabilityCount",
    "TimeoutSec",
    "PollIntervalSec",
    "HeadlessFlag",
    "Mode",
    "EventName",
    "EventTimestamp",
    "EventId",
    "EventDetails",
    "EventOrderMap",
    "ProcessingStatus",
    "ProcessingOutcome",
    "TypingDelayMs",
    "WaitTimeoutMs",
    "ClickTimeoutMs",
    "BackoffDelaySec",
    "MaxRetries",
    "StabilityChecks",
    "MinTextLength",
    "MaxFileSizeMb",
    "DropdownTimeoutMs",
    "OptionTimeoutMs",
    "FileChooserTimeoutMs",
    "CardRenderTimeoutMs",
    "InputChars",
    "OutputChars",
    "IncludeHeaderFlag",
    "GenerateSidecarFlag",
    "AtomicWriteFlag",
    "ChromeProfile",
    "ConfigPath",
    "DisableSandboxFlag",
    "UserAgent",
    "ServerName",
    "ServiceName",
    "Environment",
    "TryEnterKeyFallbackFlag",
    "FailureThreshold",
    "WindowSec",
    "MaxPerMinute",
    "FileSizeBytes",
    "LoggerName",
    "ExitCode",
    "RunContext",
    "StatusRecordVO",
    *_LEGACY_EVENT_EXPORTS,
    *_LEGACY_ERROR_EXPORTS,
]
