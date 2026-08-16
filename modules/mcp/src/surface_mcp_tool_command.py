"""MCP surface: tool handlers (AES406).

Smart surface: 4 tools delegating to the shared core orchestrators over stdio JSON-RPC.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    HeadlessFlag,
    PromptText,
    ResponseText,
    TimeoutSec,
)

if TYPE_CHECKING:
    from modules.core.src.root_core_container import SharedContainer


class McpToolCommand:
    """MCP tool dispatcher — delegates to the shared core container."""

    def __init__(self, container: SharedContainer) -> None:
        """Inject the shared container."""
        self._container = container

    def process_direct_prompt(
        self, prompt: str, timeout_sec: int = 120, headless: bool = True
    ) -> ResponseText:
        """Process a direct text prompt string."""
        return self._container.agent_direct_prompt_orchestrator.process_direct_prompt(
            PromptText(prompt), TimeoutSec(timeout_sec), HeadlessFlag(headless)
        )

    def process_prompt_file_only(
        self,
        input_file: str,
        output_file: str | None = None,
        headless: bool = True,
    ) -> ResponseText:
        """Process a prompt file from disk without attachment."""
        return self._container.agent_prompt_file_orchestrator.process_prompt_file_only(
            FilePath(input_file),
            FilePath(output_file) if output_file else None,
            HeadlessFlag(headless),
        )

    def process_prompt_with_attachment(
        self,
        prompt_file: str,
        attachment_file: str,
        output_file: str | None = None,
        headless: bool = True,
    ) -> ResponseText:
        """Process a prompt file from disk with document attachment."""
        return self._container.agent_attachment_prompt_orchestrator.process_prompt_with_attachment(
            FilePath(prompt_file),
            FilePath(attachment_file),
            FilePath(output_file) if output_file else None,
            HeadlessFlag(headless),
        )

    def setup_session(self) -> ResponseText:
        """Launch a visible browser for manual login / session setup."""
        return self._container.agent_session_orchestrator.setup_session()

    def init_workspace(self, target_dir: str = ".") -> ResponseText:
        """Initialize workspace directory structure, SKILL.md guide, sample prompt/file, and .gitignore."""
        self._container.workspace.init_workspace(FilePath(target_dir))
        return ResponseText(f"Workspace initialized successfully at {target_dir}")
