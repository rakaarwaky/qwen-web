"""MCP surface: tool handlers (AES406).

Smart surface: 6 tools delegating to the MCP aggregate over stdio JSON-RPC.
"""

from __future__ import annotations

from modules.shared.src.contract_mcp_aggregate import IMcpAggregate


class McpToolCommand:
    """MCP tool dispatcher — delegates to the MCP aggregate."""

    def __init__(self, mcp: IMcpAggregate) -> None:
        """Inject the MCP aggregate."""
        self._mcp = mcp

    def send_prompt(self, prompt: str, timeout_sec: int = 120, headless: bool = True) -> str:
        """Send a direct text prompt to chat.qwen.ai and return the AI answer."""
        return self._mcp.send_prompt(prompt, timeout_sec, headless)

    def process_single(
        self,
        input_file: str,
        output_file: str | None = None,
        headless: bool = True,
    ) -> str:
        """Process a single Markdown prompt file."""
        return self._mcp.process_single(input_file, output_file, headless)

    def process_batch(
        self,
        input_dir: str | None = None,
        output_dir: str | None = None,
        headless: bool = True,
    ) -> str:
        """Process all prompt files inside an input directory."""
        return self._mcp.process_batch(input_dir, output_dir, headless)

    def start_watcher(self, interval_sec: int = 3, headless: bool = True) -> str:
        """Run the folder watcher loop."""
        return self._mcp.start_watcher(interval_sec, headless)

    def setup_session(self) -> str:
        """Launch a visible browser for manual login / session setup."""
        return self._mcp.setup_session()

    def get_audit_log(self, limit: int = 20) -> str:
        """Fetch recent entries from the JSONL audit trail log."""
        return self._mcp.get_audit_log(limit)
