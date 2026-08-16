"""MCP surface: tool handlers (AES406).

Smart surface: tools delegating to individual agent contracts over stdio JSON-RPC.
"""

from __future__ import annotations

from modules.shared.src.contract_core_aggregate import (
    IAttachmentPromptAggregate,
    IDirectPromptAggregate,
    IPromptFileAggregate,
    ISessionAggregate,
)
from modules.shared.src.contract_core_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    HeadlessFlag,
    PromptText,
    ResponseText,
    TimeoutSec,
)


class McpToolCommand:
    """MCP tool dispatcher — delegates to individual agent contracts."""

    def __init__(
        self,
        direct: IDirectPromptAggregate,
        file_only: IPromptFileAggregate,
        attachment: IAttachmentPromptAggregate,
        session: ISessionAggregate,
        workspace: IWorkspaceProtocol,
    ) -> None:
        """Inject the individual agent aggregate contracts."""
        self._direct = direct
        self._file_only = file_only
        self._attachment = attachment
        self._session = session
        self._workspace = workspace

    def process_direct_prompt(
        self, prompt: str, timeout_sec: int = 120, headless: bool = True
    ) -> ResponseText:
        """Process a direct text prompt string."""
        return self._direct.process_direct_prompt(
            PromptText(prompt), TimeoutSec(timeout_sec), HeadlessFlag(headless)
        )

    def process_prompt_file_only(
        self,
        input_file: str,
        output_file: str | None = None,
        headless: bool = True,
    ) -> ResponseText:
        """Process a prompt file from disk without attachment."""
        return self._file_only.process_prompt_file_only(
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
        return self._attachment.process_prompt_with_attachment(
            FilePath(prompt_file),
            FilePath(attachment_file),
            FilePath(output_file) if output_file else None,
            HeadlessFlag(headless),
        )

    def setup_session(self) -> ResponseText:
        """Launch a visible browser for manual login / session setup."""
        return self._session.setup_session()

    def init_workspace(self, target_dir: str = ".") -> ResponseText:
        """Initialize workspace directory structure, SKILL.md guide, sample prompt/file, and .gitignore."""
        self._workspace.init_workspace(FilePath(target_dir))
        return ResponseText(f"Workspace initialized successfully at {target_dir}")
