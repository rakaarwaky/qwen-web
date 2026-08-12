"""MCP aggregate contract — 1:1 CLI feature tools.

Taxonomy layer (contract(aggregate)): depends only on taxonomy + contract(protocol).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IMcpAggregate(ABC):
    """MCP-specific aggregate (tools exposed over stdio JSON-RPC)."""

    @abstractmethod
    def send_prompt(self, prompt: str, timeout_sec: int = 120, headless: bool = True) -> str:
        """Send a direct text prompt."""

    @abstractmethod
    def process_single(
        self,
        input_file: str,
        output_file: str | None = None,
        headless: bool = True,
    ) -> str:
        """Process a single file."""

    @abstractmethod
    def process_batch(
        self,
        input_dir: str | None = None,
        output_dir: str | None = None,
        headless: bool = True,
    ) -> str:
        """Process a batch directory."""

    @abstractmethod
    def start_watcher(self, interval_sec: int = 3, headless: bool = True) -> str:
        """Run the folder watcher."""

    @abstractmethod
    def setup_session(self) -> str:
        """Manual login / session setup."""

    @abstractmethod
    def get_audit_log(self, limit: int = 20) -> str:
        """Fetch audit log entries."""


__all__ = ["IMcpAggregate"]
