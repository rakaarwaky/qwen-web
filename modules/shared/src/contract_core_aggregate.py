"""Core aggregate contract — the single business-logic API for all surfaces.

Taxonomy layer (contract(aggregate)): implemented by the agent orchestrator and
consumed by both the CLI and MCP surfaces. Depends only on taxonomy +
contract(protocol). The CLI and MCP features are 1:1 — they share this one
aggregate; surfaces only handle front-end concerns (arg parsing, TUI, JSON-RPC).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from modules.shared.src.taxonomy_config_vo import AppConfig


class ICoreAggregate(ABC):
    """Core processing aggregate consumed by CLI and MCP surfaces."""

    # ─── Processing API (used by CLI run + MCP tools) ───────────
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

    # ─── Workspace API (used by the CLI surface) ─────────────────
    @abstractmethod
    def init_workspace(self, target_dir: Path | str = ".") -> None:
        """Initialize the workspace (.agents/skills + .qwen-web symlinks)."""

    @abstractmethod
    def interactive_prompt(self) -> AppConfig | None:
        """Display the interactive TUI and build an AppConfig."""

    @abstractmethod
    def run_manual_login(self, cfg: AppConfig) -> None:
        """Open a visible browser for manual login."""


__all__ = ["ICoreAggregate", "AppConfig"]
