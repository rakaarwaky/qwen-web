"""Stateful domain entities: circuit breaker, rate limiter, lifecycle emitter.

Taxonomy layer (taxonomy(entity)): identity-bearing stateful entities, no I/O.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable

from modules.shared.src.taxonomy_core_constant import MAX_ATTEMPTS
from modules.shared.src.taxonomy_core_vo import (
    EVENT_DESCRIPTIONS,
    CallbackRegistry,
    EventDetails,
    EventMessage,
    FailureThreshold,
    LifecycleCallback,
    LifecycleEvent,
    MaxPerMinute,
    QwenEventType,
    WindowSec,
)


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

    def _refresh_state(self, now: float | None = None) -> None:
        """Discard expired failures and recompute the trip state."""
        current = time.time() if now is None else now
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
    """Mutable run-local gates driven only by emitted lifecycle events."""

    def __init__(self) -> None:
        self.web_loaded = False
        self.document_parsed = False
        self.dispatch_acknowledged = False

    def mark(self, event_name: QwenEventType | str) -> None:
        """Advance exactly the gate represented by an emitted event."""
        if event_name == QwenEventType.WEB_LOADED:
            self.web_loaded = True
        elif event_name == QwenEventType.DOCUMENT_PARSED:
            self.document_parsed = True
        elif event_name == QwenEventType.DISPATCH_ACKNOWLEDGED:
            self.dispatch_acknowledged = True


class LifecycleEmitter:
    """Event bus for pipeline lifecycle events with typed dispatcher capability."""

    def __init__(self, logger: Callable[..., object] | None = None) -> None:
        """Initialize with an empty callback registry and an optional logger."""
        self._callbacks: CallbackRegistry = {}
        self._logger = logger or logging.getLogger("lifecycle")

    def on(self, event_name: QwenEventType | str, callback: LifecycleCallback) -> None:
        """Register a callback for a named lifecycle event."""
        key = str(event_name)
        self._callbacks.setdefault(key, []).append(callback)

    def emit(self, event_name: QwenEventType | str, details: EventDetails | None = None) -> LifecycleEvent:
        """Emit a lifecycle event to all registered callbacks."""
        key = str(event_name)
        evt = LifecycleEvent(
            name=key,
            timestamp=time.time(),
            details=details or {},
        )
        enum_member = event_name if isinstance(event_name, QwenEventType) else None
        label = EVENT_DESCRIPTIONS.get(enum_member, key) if enum_member else key
        detail_str = f" - {details}" if details else ""
        self._log(EventMessage(f"[{key}] {label}{detail_str}"))
        for cb in self._callbacks.get(key, []):
            try:
                cb(evt)
            except Exception as exc:  # third-party callbacks may raise anything; must not break emission
                self._log(EventMessage(f"lifecycle_callback_error event={key} error={exc}"))
        return evt

    def _log(self, message: EventMessage) -> None:
        """Log a message via the injected logger (callable or .info())."""
        if callable(self._logger):
            self._logger(message)
        else:
            self._logger.info(message)
