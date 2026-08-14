"""Stateful domain entities: circuit breaker, rate limiter, lifecycle emitter.

Taxonomy layer (taxonomy(entity)): identity-bearing stateful entities, no I/O.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable

from modules.shared.src.taxonomy_core_constant import MAX_ATTEMPTS
from modules.shared.src.taxonomy_core_event import (
    EVENT_DESCRIPTIONS,
    EVENT_ORDER,
    PIPELINE_EVENT_SEQUENCE,
    CallbackRegistry,
    EventDetails,
    EventMessage,
    LifecycleCallback,
    LifecycleEvent,
    QwenEventType,
)
from modules.shared.src.taxonomy_core_vo import FailureThreshold, MaxPerMinute, WindowSec


# Lifecycle gate: define required predecessor for each event
LIFECYCLE_GATES: dict[QwenEventType, QwenEventType | None] = {
    QwenEventType.NETWORK_RECONNECTING: None,
    QwenEventType.WEB_LOADED: None,
    QwenEventType.FILE_UPLOADED: QwenEventType.WEB_LOADED,
    QwenEventType.PROMPT_INJECTED: QwenEventType.FILE_UPLOADED,
    QwenEventType.DOCUMENT_PARSED: QwenEventType.PROMPT_INJECTED,
    QwenEventType.SEND_CLICKED: QwenEventType.DOCUMENT_PARSED,
    QwenEventType.DISPATCH_ACKNOWLEDGED: QwenEventType.SEND_CLICKED,
    QwenEventType.THINKING_STARTED: QwenEventType.DISPATCH_ACKNOWLEDGED,
    QwenEventType.STREAMING_GENERATION: QwenEventType.THINKING_STARTED,
    QwenEventType.GENERATION_FINISHED: QwenEventType.STREAMING_GENERATION,
    QwenEventType.OUTPUT_COPIED: QwenEventType.GENERATION_FINISHED,
}


class CircuitBreaker:
    """Sliding-window circuit breaker for request-level failure tracking."""

    def __init__(
        self,
        threshold: FailureThreshold = FailureThreshold(MAX_ATTEMPTS),
        window_sec: WindowSec = WindowSec(30),
    ) -> None:
        """Initialize circuit breaker with sliding-window failure threshold.

        Args:
            threshold: Number of failures within window_sec to trip the breaker.
            window_sec: Sliding time window in seconds for counting failures.

        Raises:
            ValueError: If threshold or window_sec < 1.

        """
        if threshold < 1:
            raise ValueError(f"threshold must be >= 1, got {threshold}")
        if window_sec < 1:
            raise ValueError(f"window_sec must be >= 1, got {window_sec}")
        self._threshold = threshold
        self._window_sec = window_sec
        self._failures: deque[float] = deque()
        self._trip: bool = False

    def configure(self, threshold: FailureThreshold, window_sec: WindowSec) -> None:
        """Update limits while preserving accumulated failure history."""
        if threshold < 1:
            raise ValueError(f"threshold must be >= 1, got {threshold}")
        if window_sec < 1:
            raise ValueError(f"window_sec must be >= 1, got {window_sec}")
        self._threshold = threshold
        self._window_sec = window_sec
        self._refresh_state()

    def _refresh_state(self) -> None:
        """Discard expired failures and recompute the trip state."""
        current = time.time()
        while self._failures and (current - self._failures[0]) > self._window_sec:
            self._failures.popleft()
        self._trip = len(self._failures) >= self._threshold

    def record_success(self) -> None:
        """Reset the breaker on a successful request."""
        self._failures.clear()
        self._trip = False

    def record_failure(self) -> None:
        """Record a failure and trip if threshold exceeded within window."""
        self._failures.append(time.time())
        self._refresh_state()

    @property
    def threshold(self) -> int:
        """Configured consecutive-failure threshold."""
        return int(self._threshold)

    @property
    def window_sec(self) -> int:
        """Configured failure observation window in seconds."""
        return int(self._window_sec)

    @property
    def is_tripped(self) -> bool:
        """True when the breaker has tripped."""
        self._refresh_state()
        return self._trip


class RateLimiter:
    """Simple token-bucket rate limiter for request throttling."""

    def __init__(self, max_per_minute: MaxPerMinute = MaxPerMinute(60)) -> None:
        """Initialize rate limiter with a fixed window of max requests per minute.

        Args:
            max_per_minute: Maximum number of acquire() calls allowed per 60-second window.

        Raises:
            ValueError: If max_per_minute < 1.

        """
        if max_per_minute < MaxPerMinute(1):
            raise ValueError(f"max_per_minute must be >= 1, got {max_per_minute}")
        self._max_per_minute = max_per_minute
        self._timestamps: deque[float] = deque()

    def configure(self, max_per_minute: MaxPerMinute) -> None:
        """Update the request limit while preserving timestamp history."""
        if max_per_minute < MaxPerMinute(1):
            raise ValueError(f"max_per_minute must be >= 1, got {max_per_minute}")
        self._max_per_minute = max_per_minute

    @property
    def max_per_minute(self) -> int:
        """Configured maximum requests per minute."""
        return int(self._max_per_minute)

    def acquire(self) -> None:
        """Wait until a request slot is available."""
        now = time.time()
        window_start = now - 60.0
        while True:
            while self._timestamps and self._timestamps[0] < window_start:
                self._timestamps.popleft()
            if len(self._timestamps) < self._max_per_minute:
                break
            oldest = self._timestamps[0]
            wait_sec = max(0.1, 60.0 - (now - oldest) + 0.1)
            time.sleep(wait_sec)
            now = time.time()
            window_start = now - 60.0
        self._timestamps.append(time.time())


class LifecycleState:
    """Mutable run-local gates driven only by emitted lifecycle events.

    Tracks all pipeline events and provides gate checking for strict
    lifecycle enforcement. Each event can only be emitted if its
    predecessor has succeeded.
    """

    def __init__(self) -> None:
        # Track all pipeline events
        self.web_loaded = False
        self.file_uploaded = False
        self.prompt_injected = False
        self.document_parsed = False
        self.send_clicked = False
        self.dispatch_acknowledged = False
        self.thinking_started = False
        self.streaming_generation = False
        self.generation_finished = False
        self.output_copied = False
        # Track failure state to halt pipeline
        self._failed = False
        self._failed_at: QwenEventType | None = None

    def mark(self, event_name: QwenEventType | str) -> None:
        """Advance exactly the gate represented by an emitted event."""
        if isinstance(event_name, str):
            event_name = QwenEventType(event_name)
        if event_name == QwenEventType.WEB_LOADED:
            self.web_loaded = True
        elif event_name == QwenEventType.FILE_UPLOADED:
            self.file_uploaded = True
        elif event_name == QwenEventType.PROMPT_INJECTED:
            self.prompt_injected = True
        elif event_name == QwenEventType.DOCUMENT_PARSED:
            self.document_parsed = True
        elif event_name == QwenEventType.SEND_CLICKED:
            self.send_clicked = True
        elif event_name == QwenEventType.DISPATCH_ACKNOWLEDGED:
            self.dispatch_acknowledged = True
        elif event_name == QwenEventType.THINKING_STARTED:
            self.thinking_started = True
        elif event_name == QwenEventType.STREAMING_GENERATION:
            self.streaming_generation = True
        elif event_name == QwenEventType.GENERATION_FINISHED:
            self.generation_finished = True
        elif event_name == QwenEventType.OUTPUT_COPIED:
            self.output_copied = True

    def mark_failed(self, at_event: QwenEventType | str | None = None) -> None:
        """Record that the pipeline failed at a specific event."""
        self._failed = True
        if at_event is not None:
            if isinstance(at_event, str):
                at_event = QwenEventType(at_event)
            self._failed_at = at_event

    @property
    def has_failed(self) -> bool:
        """Return True if the pipeline has recorded a failure."""
        return self._failed

    @property
    def failed_at(self) -> QwenEventType | None:
        """Return the event where failure occurred, or None."""
        return self._failed_at

    def can_emit(self, event_name: QwenEventType | str) -> bool:
        """Check if an event can be emitted based on lifecycle gates.

        Returns True only if:
        1. The pipeline has not failed
        2. The event's predecessor has been successfully emitted
        3. The event is not a known pipeline event (allows arbitrary events)
        """
        if self._failed:
            return False
        if isinstance(event_name, str):
            try:
                event_name = QwenEventType(event_name)
            except ValueError:
                # Unknown event - allow it to pass through
                return True

        required = LIFECYCLE_GATES.get(event_name)
        if required is None:
            # No predecessor required (e.g., WEB_LOADED)
            return True

        return self._has_emitted(required)

    def _has_emitted(self, event: QwenEventType) -> bool:
        """Check if a specific event has been emitted."""
        if event == QwenEventType.WEB_LOADED:
            return self.web_loaded
        elif event == QwenEventType.FILE_UPLOADED:
            return self.file_uploaded
        elif event == QwenEventType.PROMPT_INJECTED:
            return self.prompt_injected
        elif event == QwenEventType.DOCUMENT_PARSED:
            return self.document_parsed
        elif event == QwenEventType.SEND_CLICKED:
            return self.send_clicked
        elif event == QwenEventType.DISPATCH_ACKNOWLEDGED:
            return self.dispatch_acknowledged
        elif event == QwenEventType.THINKING_STARTED:
            return self.thinking_started
        elif event == QwenEventType.STREAMING_GENERATION:
            return self.streaming_generation
        elif event == QwenEventType.GENERATION_FINISHED:
            return self.generation_finished
        elif event == QwenEventType.OUTPUT_COPIED:
            return self.output_copied
        return False


class LifecycleEmitter:
    """Event bus for pipeline lifecycle events with typed dispatcher capability.

    Supports strict lifecycle gates through an optional LifecycleState.
    When a state is attached via attach_state(), events can only be emitted
    if their predecessor has succeeded.
    """

    def __init__(self, logger: Callable[..., object] | None = None) -> None:
        """Initialize with an empty callback registry and an optional logger."""
        self._callbacks: CallbackRegistry = {}
        self._logger = logger or logging.getLogger("lifecycle")
        self._state: LifecycleState | None = None

    def attach_state(self, state: LifecycleState) -> None:
        """Attach a LifecycleState for gate enforcement.

        When a state is attached, can_emit() and emit() will enforce
        that each event's predecessor has been successfully emitted.
        """
        self._state = state

    def detach_state(self) -> None:
        """Detach the LifecycleState, disabling gate enforcement."""
        self._state = None

    def can_emit(self, event_name: QwenEventType | str) -> bool:
        """Check if an event can be emitted based on lifecycle gates.

        If no state is attached, always returns True.
        If state is attached, checks that predecessor events have succeeded.
        """
        if self._state is None:
            return True
        return self._state.can_emit(event_name)

    def on(self, event_name: QwenEventType | str, callback: LifecycleCallback) -> None:
        """Register a callback for a named lifecycle event."""
        key = str(event_name)
        self._callbacks.setdefault(key, []).append(callback)

    def emit(
        self,
        event_name: QwenEventType | str,
        details: EventDetails | None = None,
        require_gate: bool = True,
    ) -> LifecycleEvent | None:
        """Emit a lifecycle event to all registered callbacks.

        If require_gate is True and a state is attached, the event will
        only be emitted if its predecessor has succeeded. Returns None
        if the gate check fails.
        """
        key = str(event_name)
        # Try to convert to enum for gate check and description lookup
        enum_event: QwenEventType | None = None
        if isinstance(event_name, QwenEventType):
            enum_event = event_name
        else:
            try:
                enum_event = QwenEventType(event_name)
            except ValueError:
                # Unknown event name - allow it to pass through without gate check
                pass

        # Gate check: prevent invalid transitions
        if require_gate and self._state is not None and enum_event is not None:
            if not self._state.can_emit(enum_event):
                self._log(
                    EventMessage(
                        f"BLOCKED: {key} cannot be emitted - "
                        f"predecessor not succeeded (pipeline failed={self._state.has_failed})"
                    )
                )
                return None

        evt = LifecycleEvent(
            name=key,
            timestamp=time.time(),
            details=details or {},
        )
        label = EVENT_DESCRIPTIONS.get(enum_event, key) if enum_event else key
        detail_str = f" - {details}" if details else ""
        self._log(EventMessage(f"[{key}] {label}{detail_str}"))

        # Mark event as emitted in state
        if self._state is not None and enum_event is not None:
            self._state.mark(enum_event)

        for cb in self._callbacks.get(key, []):
            try:
                cb(evt)
            except Exception as exc:  # third-party callbacks may raise anything; must not break emission
                self._log(EventMessage(f"lifecycle_callback_error event={key} error={exc}"))
        return evt

    def emit_if_allowed(
        self,
        event_name: QwenEventType | str,
        details: EventDetails | None = None,
    ) -> LifecycleEvent | None:
        """Emit an event only if the gate check passes. Alias for emit with require_gate=True."""
        return self.emit(event_name, details, require_gate=True)

    def _log(self, message: EventMessage) -> None:
        """Log a message via the injected logger (callable or .info())."""
        if callable(self._logger):
            self._logger(message)
        else:
            self._logger.info(message)
