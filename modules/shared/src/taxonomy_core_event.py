"""Taxonomy definitions for qwen-web lifecycle events.

This module contains only event values and immutable event payload contracts.
Stateful event emission and lifecycle state live in ``taxonomy_core_entity``.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import NewType

from .taxonomy_core_vo import EventDetails, EventId, EventName, EventOrderMap, EventTimestamp


class QwenEventType(str, Enum):
    """Ordered lifecycle events emitted by the qwen-web pipeline."""

    def __str__(self) -> str:
        """Return the wire name of the event."""
        return str(self.value)

    NETWORK_RECONNECTING = "EVENT_NETWORK_RECONNECTING"
    WEB_LOADED = "EVENT_WEB_LOADED"
    FILE_UPLOADED = "EVENT_FILE_UPLOADED"
    PROMPT_INJECTED = "EVENT_PROMPT_INJECTED"
    DOCUMENT_PARSED = "EVENT_DOCUMENT_PARSED"
    SEND_CLICKED = "EVENT_SEND_CLICKED"
    DISPATCH_ACKNOWLEDGED = "EVENT_DISPATCH_ACKNOWLEDGED"
    THINKING_STARTED = "EVENT_THINKING_STARTED"
    STREAMING_GENERATION = "EVENT_STREAMING_GENERATION"
    GENERATION_FINISHED = "EVENT_GENERATION_FINISHED"
    OUTPUT_COPIED = "EVENT_OUTPUT_COPIED"


EVENT_NETWORK_RECONNECTING = QwenEventType.NETWORK_RECONNECTING
EVENT_WEB_LOADED = QwenEventType.WEB_LOADED
EVENT_FILE_UPLOADED = QwenEventType.FILE_UPLOADED
EVENT_PROMPT_INJECTED = QwenEventType.PROMPT_INJECTED
EVENT_DOCUMENT_PARSED = QwenEventType.DOCUMENT_PARSED
EVENT_SEND_CLICKED = QwenEventType.SEND_CLICKED
EVENT_DISPATCH_ACKNOWLEDGED = QwenEventType.DISPATCH_ACKNOWLEDGED
EVENT_THINKING_STARTED = QwenEventType.THINKING_STARTED
EVENT_STREAMING_GENERATION = QwenEventType.STREAMING_GENERATION
EVENT_GENERATION_FINISHED = QwenEventType.GENERATION_FINISHED
EVENT_OUTPUT_COPIED = QwenEventType.OUTPUT_COPIED


PIPELINE_EVENT_SEQUENCE: tuple[QwenEventType, ...] = (
    QwenEventType.WEB_LOADED,
    QwenEventType.FILE_UPLOADED,
    QwenEventType.PROMPT_INJECTED,
    QwenEventType.DOCUMENT_PARSED,
    QwenEventType.SEND_CLICKED,
    QwenEventType.THINKING_STARTED,
    QwenEventType.STREAMING_GENERATION,
    QwenEventType.GENERATION_FINISHED,
    QwenEventType.OUTPUT_COPIED,
)

EVENT_ORDER: EventOrderMap = EventOrderMap({event: index for index, event in enumerate(PIPELINE_EVENT_SEQUENCE)})


@dataclass
class LifecycleEvent:
    """Structured event emitted at a lifecycle boundary."""

    name: EventName
    timestamp: EventTimestamp = field(default_factory=lambda: EventTimestamp(time.time()))
    event_id: EventId = field(default_factory=lambda: EventId(uuid.uuid4().hex))
    details: EventDetails = field(default_factory=EventDetails)


LifecycleCallback = Callable[[LifecycleEvent], None]
EventMessage = NewType("EventMessage", str)
CallbackRegistry = dict[str, list[LifecycleCallback]]


EVENT_DESCRIPTIONS: dict[QwenEventType, str] = {
    QwenEventType.NETWORK_RECONNECTING: "Reconnecting to Qwen Web...",
    QwenEventType.WEB_LOADED: "Qwen Web page loaded",
    QwenEventType.FILE_UPLOADED: "Prompt file uploaded",
    QwenEventType.PROMPT_INJECTED: "Prompt injected into the composer",
    QwenEventType.DOCUMENT_PARSED: "Prompt/document parsed",
    QwenEventType.SEND_CLICKED: "Send button clicked",
    QwenEventType.DISPATCH_ACKNOWLEDGED: "Dispatch acknowledged",
    QwenEventType.THINKING_STARTED: "Qwen AI thinking...",
    QwenEventType.STREAMING_GENERATION: "Qwen AI typing...",
    QwenEventType.GENERATION_FINISHED: "Generation finished",
    QwenEventType.OUTPUT_COPIED: "Output saved",
}

__all__ = [
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
]
