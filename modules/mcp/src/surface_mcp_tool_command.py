"""MCP surface: tool handlers (AES406).

Smart surface: 6 tools delegating to the shared core aggregate over stdio JSON-RPC.
"""

from __future__ import annotations

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    HeadlessFlag,
    MessageCount,
    PromptText,
    ResponseText,
    TimeoutSec,
)


class McpToolCommand:
    """MCP tool dispatcher — delegates to the core aggregate."""

    def __init__(self, core: ICoreAggregate) -> None:
        """Inject the core aggregate."""
        self._core = core

    def send_prompt(self, prompt: str, timeout_sec: int = 120, headless: bool = True) -> ResponseText:
        """Send a direct text prompt to chat.qwen.ai and return the AI answer."""
        return self._core.send_prompt(PromptText(prompt), TimeoutSec(timeout_sec), HeadlessFlag(headless))

    def process_single(
        self,
        input_file: str,
        output_file: str | None = None,
        headless: bool = True,
    ) -> ResponseText:
        """Process a single Markdown prompt file."""
        return self._core.process_single_file(
            FilePath(input_file), FilePath(output_file) if output_file else None, HeadlessFlag(headless)
        )

    def setup_session(self) -> ResponseText:
        """Launch a visible browser for manual login / session setup."""
        return self._core.setup_session()

    def get_audit_log(self, limit: int = 20) -> ResponseText:
        """Fetch recent entries from the JSONL audit trail log."""
        return self._core.get_audit_log(MessageCount(limit))
