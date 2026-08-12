"""Core qwen-web domain value objects: run context, lifecycle events, and enums.

Taxonomy layer (taxonomy(vo)): frozen dataclasses and enums, no I/O.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

RunContextId = str


@dataclass
class RunContext:
    """Run-scoped context with auto-generated run ID.

    Attributes
    ----------
    run_id : str
        Unique identifier: YYYYMMDD_HHMMSS_randomhex[:6].

    """

    run_id: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S_")
        + uuid.uuid4().hex[:6]
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
