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
from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    MessageCount,
    PromptText,
    ResponseText,
    TimeoutSec,
)


class ICoreAggregate(ABC):
    """Core processing aggregate consumed by CLI and MCP surfaces."""

    # ─── Processing API (used by CLI run + MCP tools) ───────────
    @abstractmethod
    def process_single_file(
        self,
        input_file: Path | FilePath,
        output_file: Path | FilePath | None = None,
        headless: bool = True,
    ) -> ResponseText:
        """Process a single prompt file."""

    @abstractmethod
    def process_batch(
        self,
        input_dir: Path | FilePath | None = None,
        output_dir: Path | FilePath | None = None,
        headless: bool = True,
    ) -> ResponseText:
        """Process a directory of prompt files."""

    @abstractmethod
    def process_watcher(
        self,
        interval_sec: TimeoutSec = TimeoutSec(3),
        headless: bool = True,
    ) -> ResponseText:
        """Run the continuous folder watcher."""

    @abstractmethod
    def process_mode(self, cfg: AppConfig) -> ResponseText:
        """Dispatch processing based on AppConfig.mode (watcher/single/batch)."""

    @abstractmethod
    def send_prompt(
        self,
        prompt: PromptText,
        timeout_sec: TimeoutSec = TimeoutSec(120),
        headless: bool = True,
    ) -> ResponseText:
        """Send a direct text prompt and return the AI response."""

    @abstractmethod
    def setup_session(self) -> ResponseText:
        """Launch a visible browser for manual login / session setup."""

    @abstractmethod
    def get_audit_log(self, limit: MessageCount = MessageCount(20)) -> ResponseText:
        """Return recent audit log entries as JSON text."""

    # ─── Workspace API (back-end; I/O delegated to capabilities) ─
    @abstractmethod
    def init_workspace(self, target_dir: Path | FilePath = FilePath(".")) -> None:
        """Initialize the workspace (.agents/skills + .qwen-web symlinks)."""


__all__ = ["ICoreAggregate"]
