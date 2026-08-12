"""Capabilities: in-memory metrics collector (AES403).

Thread-safe counter for tracking request counts, errors, and other numeric metrics.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any


class MetricsCounter:
    """Thread-safe in-memory metrics collector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._start_time = datetime.now(tz=timezone.utc)

    def increment(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + amount

    def get(self, key: str) -> int:
        with self._lock:
            return self._counters.get(key, 0)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._counters)


# Module-level convenience
def counter() -> MetricsCounter:
    """Create a fresh metrics counter (module-level convenience)."""
    return MetricsCounter()
