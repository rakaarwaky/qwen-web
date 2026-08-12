"""Capabilities: in-memory metrics collector (AES403).

Implements IMetricsProtocol — thread-safe counter for tracking request counts,
errors, and other numeric metrics.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from modules.shared.src.contract_metrics_protocol import IMetricsProtocol
from modules.shared.src.taxonomy_core_vo import MessageCount


# Block 1: Class Definition & Constructor ──────────────
class MetricsCounter(IMetricsProtocol):
    """Thread-safe in-memory metrics collector.

    In-memory dict with thread lock — fast for local counters,
    not persisted across restarts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._start_time = datetime.now(tz=timezone.utc)

    # ─── Block 2: Public Contract (IMetricsProtocol ONLY) ──
    def increment(self, key: str, amount: MessageCount = MessageCount(1)) -> None:
        with self._lock:
            self._counters[key] = self._counters.get(key, MessageCount(0)) + amount

    def get(self, key: str) -> MessageCount:
        with self._lock:
            return MessageCount(self._counters.get(key, 0))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._counters)

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────
    def __repr__(self) -> str:
        return "MetricsCounter()"


# Module-level convenience
def counter() -> MetricsCounter:
    """Create a fresh metrics counter (module-level convenience)."""
    return MetricsCounter()
