"""Status file protocol (contract layer).

Taxonomy layer (contract(protocol)): pure ABC, signatures use VOs.
Capabilities implement these; agents/surfaces depend on them via DI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IStatusProtocol(ABC):
    """Status file write/read capability contract."""

    @abstractmethod
    def write(self, **kwargs: Any) -> None:
        """Atomically write status to disk."""

    @abstractmethod
    def write_record(self, record: Any) -> None:
        """Atomically write a record to disk."""

    @abstractmethod
    def read(self) -> dict[str, Any] | None:
        """Read and return the current status record."""


__all__ = ["IStatusProtocol"]
