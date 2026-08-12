"""Stateful domain entities: circuit breaker and rate limiter.

Taxonomy layer (taxonomy(entity)): identity-bearing stateful entities, no I/O.
"""

from __future__ import annotations

import time
from collections import deque


class CircuitBreaker:
    """Sliding-window circuit breaker for request-level failure tracking."""

    def __init__(self, threshold: int = 5, window_sec: int = 30) -> None:
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

    def record_success(self) -> None:
        """Reset the breaker on a successful request."""
        self._failures.clear()
        self._trip = False

    def record_failure(self) -> None:
        """Record a failure and trip if threshold exceeded within window."""
        now = time.time()
        self._failures.append(now)
        while self._failures and (now - self._failures[0]) > self._window_sec:
            self._failures.popleft()
        if len(self._failures) >= self._threshold:
            self._trip = True

    @property
    def is_tripped(self) -> bool:
        """True when the breaker has tripped."""
        return self._trip


class RateLimiter:
    """Simple token-bucket rate limiter for request throttling."""

    def __init__(self, max_per_minute: int = 60) -> None:
        """Initialize rate limiter with a fixed window of max requests per minute.

        Args:
            max_per_minute: Maximum number of acquire() calls allowed per 60-second window.

        Raises:
            ValueError: If max_per_minute < 1.

        """
        if max_per_minute < 1:
            raise ValueError(f"max_per_minute must be >= 1, got {max_per_minute}")
        self._max_per_minute = max_per_minute
        self._timestamps: deque[float] = deque()

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
