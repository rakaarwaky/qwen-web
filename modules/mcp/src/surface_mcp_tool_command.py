"""MCP surface: tool handlers (AES406).

Smart surface: 4 tools delegating to the shared core aggregate over stdio JSON-RPC.
"""

from __future__ import annotations

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    HeadlessFlag,
    PromptText,
    ResponseText,
    TimeoutSec,
)


class McpToolCommand:
    """MCP tool dispatcher — delegates to the core aggregate."""

    def __init__(self, core: ICoreAggregate) -> None:
        """Inject the core aggregate."""
        self._core = core

    def process_direct_prompt(
        self, prompt: str, timeout_sec: int = 120, headless: bool = True
    ) -> ResponseText:
        """Process a direct text prompt string."""
        return self._core.process_direct_prompt(
            PromptText(prompt), TimeoutSec(timeout_sec), HeadlessFlag(headless)
        )

    def process_prompt_file_only(
        self,
        input_file: str,
        output_file: str | None = None,
        headless: bool = True,
    ) -> ResponseText:
        """Process a prompt file from disk without attachment."""
        return self._core.process_prompt_file_only(
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
        return self._core.process_prompt_with_attachment(
            FilePath(prompt_file),
            FilePath(attachment_file),
            FilePath(output_file) if output_file else None,
            HeadlessFlag(headless),
        )

    def setup_session(self) -> ResponseText:
        """Launch a visible browser for manual login / session setup."""
        return self._core.setup_session()

    def init_workspace(self, target_dir: str = ".") -> ResponseText:
        """Initialize workspace directory structure, SKILL.md guide, sample prompt/file, and .gitignore."""
        self._core.init_workspace(FilePath(target_dir))
        return ResponseText(f"Workspace initialized successfully at {target_dir}")
