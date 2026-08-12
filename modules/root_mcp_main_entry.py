#!/usr/bin/env python3
"""qwen-web MCP server entry point.

Root layer: bootstraps the FastMCP server over stdio with the wired MCP
container. The 6 tools are registered on the FastMCP instance, delegating
to the MCP aggregate.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

try:
    from fastmcp import FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = None

from modules.mcp.src.root_mcp_container import McpContainer
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG


def _isolate_thread_event_loop() -> None:
    """Ensure the worker thread has an isolated event loop for Playwright sync_api."""
    import asyncio
    try:
        if hasattr(asyncio, "_set_running_loop"):
            asyncio._set_running_loop(None)
    except Exception:
        pass
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception:
        pass


def _register_tools(container: McpContainer, mcp: Any) -> None:
    """Register all 6 MCP tools on the FastMCP instance."""
    mcp_tools = container.mcp
    tool: Callable[..., Callable[[Callable[..., Any]], Callable[..., Any]]] = mcp.tool

    @tool()
    async def qwen_send_prompt(
        prompt: str,
        timeout_sec: int = 120,
        headless: bool = True,
    ) -> str:
        """Send a direct text prompt string to chat.qwen.ai and return AI answer."""
        import asyncio
        return await asyncio.to_thread(mcp_tools.send_prompt, prompt, timeout_sec, headless)

    @tool()
    async def qwen_process_single(
        input_file: str,
        output_file: str | None = None,
        headless: bool = True,
    ) -> str:
        """Process a single Markdown prompt file (1:1 CLI Single File Mode)."""
        import asyncio
        return await asyncio.to_thread(mcp_tools.process_single, input_file, output_file, headless)

    @tool()
    async def qwen_process_batch(
        input_dir: str | None = None,
        output_dir: str | None = None,
        headless: bool = True,
    ) -> str:
        """Process all prompt files inside an input directory (1:1 CLI Batch Mode)."""
        import asyncio
        return await asyncio.to_thread(mcp_tools.process_batch, input_dir, output_dir, headless)

    @tool()
    async def qwen_start_watcher(interval_sec: int = 3, headless: bool = True) -> str:
        """Run folder watcher loop to continuously monitor input/ for new files."""
        import asyncio
        return await asyncio.to_thread(mcp_tools.start_watcher, interval_sec, headless)

    @tool()
    async def qwen_setup_session() -> str:
        """Launch visible browser on chat.qwen.ai for manual login / session setup."""
        import asyncio
        return await asyncio.to_thread(mcp_tools.setup_session)

    @tool()
    def qwen_get_audit_log(limit: int = 20) -> str:
        """Fetch latest entries from the JSONL audit trail log."""
        return mcp_tools.get_audit_log(limit)


def run_mcp_server() -> None:
    """Run the FastMCP server over stdio."""
    if FastMCP is None:
        raise ImportError(
            "The 'mcp' Python package is required to run the MCP server. Install it via 'pip install mcp'."
        )

    from modules.core.src.capabilities_observability import setup_observability

    setup_observability(DEFAULT_LOG)

    # Redirect standard text prints & logging to stderr to protect JSON-RPC stdio
    sys.stdout = sys.stderr

    mcp = FastMCP("Qwen-Web")
    container = McpContainer()
    container.wire()
    _register_tools(container, mcp)

    # Restore sys.stdout to sys.__stdout__ (FD 1) for FastMCP stdio transport
    sys.stdout = sys.__stdout__
    mcp.run()


def main() -> None:
    """Entry point for the qwen-web MCP server."""
    run_mcp_server()


if __name__ == "__main__":
    main()
