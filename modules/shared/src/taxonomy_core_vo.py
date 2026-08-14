"""Core qwen-web domain value objects: brand (NewType) types, run context,
Core value objects only.

Taxonomy layer (taxonomy(vo)): immutable value contracts and brand aliases — no I/O.
Lifecycle events live in taxonomy_core_event; domain errors live in taxonomy_core_error.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import NewType

from .taxonomy_core_error import ErrorCategory  # noqa: F401
from .taxonomy_core_event import *  # noqa: F403

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


# Compatibility re-exports are imported at module top; new code should use
# taxonomy_core_event directly.


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


# ErrorCategory is imported at module top for the legacy path.
