"""Core aggregate contract — top-level feature orchestration API.

Taxonomy layer (contract(aggregate)): implemented by the agent orchestrator and
consumed by CLI/MCP surfaces. Depends only on taxonomy + contract(protocol).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class ICoreAggregate(ABC):
    """Core processing aggregate consumed by surfaces."""

    @abstractmethod
    def process_single_file(
        self,
        input_file: Path | str,
        output_file: Path | str | None = None,
        headless: bool = True,
    ) -> str:
        """Process a single prompt file."""

    @abstractmethod
    def process_batch(
        self,
        input_dir: Path | str | None = None,
        output_dir: Path | str | None = None,
        headless: bool = True,
    ) -> str:
        """Process a directory of prompt files."""

    @abstractmethod
    def process_watcher(self, interval_sec: int = 3, headless: bool = True) -> str:
        """Run the continuous folder watcher."""

    @abstractmethod
    def send_prompt(self, prompt: str, timeout_sec: int = 120, headless: bool = True) -> str:
        """Send a direct text prompt and return the AI response."""

    @abstractmethod
    def setup_session(self) -> str:
        """Launch a visible browser for manual login / session setup."""

    @abstractmethod
    def get_audit_log(self, limit: int = 20) -> str:
        """Return recent audit log entries as JSON text."""


__all__ = ["ICoreAggregate"]
