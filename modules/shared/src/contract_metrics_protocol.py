"""Metrics collection protocol (contract layer).

Taxonomy layer (contract(protocol)): pure ABC, signatures use VOs.
Capabilities implement these; agents/surfaces depend on them via DI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IMetricsProtocol(ABC):
    """In-memory metrics collection capability contract."""

    @abstractmethod
    def increment(self, key: str, amount: int = 1) -> None:
        """Increment a counter by the given amount."""

    @abstractmethod
    def get(self, key: str) -> int:
        """Return the current value of a counter."""

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Return a shallow copy of all counters."""


__all__ = ["IMetricsProtocol"]
