"""Contract: aggregate interfaces for core domain (AES402)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..common.taxonomy_core_vo import Mode


class ICoreAggregate(ABC):
    """Aggregate for core Qwen processing operations (implemented by CoreOrchestrator)."""

    @abstractmethod
    def process_single_file(
        self,
        input_path: Path,
        output_path: Path | None = None,
    ) -> dict[str, Any]:
        """Process a single prompt file through Qwen Web."""
        ...

    @abstractmethod
    def process_batch(
        self,
        input_dir: Path,
        output_dir: Path | None = None,
        done_dir: Path | None = None,
        failed_dir: Path | None = None,
    ) -> dict[str, Any]:
        """Process all prompt files in an input directory."""
        ...

    @abstractmethod
    def process_watcher(
        self,
        input_dir: Path,
        interval_sec: int = 3,
    ) -> None:
        """Run continuous watcher loop for new files."""
        ...

    @abstractmethod
    def send_prompt(
        self,
        prompt: str,
        timeout_sec: int = 120,
    ) -> str:
        """Send a direct text prompt and return the response."""
        ...

    @abstractmethod
    def setup_session(
        self,
        headless: bool = False,
    ) -> dict[str, Any]:
        """Set up browser session (for login flow)."""
        ...


class ICliAggregate(ABC):
    """Aggregate for CLI-specific operations."""

    @abstractmethod
    def init_workspace(self, target_dir: Path) -> dict[str, Any]:
        """Initialize workspace with .agents/skills and .qwen-web symlinks."""
        ...

    @abstractmethod
    def run_login_flow(self) -> dict[str, Any]:
        """Launch visible browser for manual login."""
        ...


class IMcpAggregate(ABC):
    """Aggregate for MCP server operations."""

    @abstractmethod
    def mcp_send_prompt(
        self,
        prompt: str,
        timeout_sec: int = 120,
        headless: bool = True,
    ) -> dict[str, Any]:
        """MCP tool: send direct prompt."""
        ...

    @abstractmethod
    def mcp_process_single(
        self,
        input_file: str,
        output_file: str | None = None,
        headless: bool = True,
    ) -> dict[str, Any]:
        """MCP tool: process single file."""
        ...

    @abstractmethod
    def mcp_process_batch(
        self,
        input_dir: str | None = None,
        output_dir: str | None = None,
        headless: bool = True,
    ) -> dict[str, Any]:
        """MCP tool: process batch."""
        ...

    @abstractmethod
    def mcp_start_watcher(
        self,
        interval_sec: int = 3,
        headless: bool = True,
    ) -> dict[str, Any]:
        """MCP tool: start watcher loop (unbounded)."""
        ...

    @abstractmethod
    def mcp_setup_session(self, headless: bool = True) -> dict[str, Any]:
        """MCP tool: setup browser session."""
        ...

    @abstractmethod
    def mcp_get_audit_log(self, limit: int = 20) -> str:
        """MCP tool: get audit history."""
        ...