#!/usr/bin/env python3
"""qwen-web MCP server entry point.

Root layer: bootstraps the FastMCP server over stdio with the wired MCP
container. The 6 tools are module-level async functions (callable directly
for tests) and are registered on the FastMCP instance, delegating to the
shared core aggregate via the MCP surface.
"""

from __future__ import annotations

import asyncio
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

# FastMCP application instance (module-level for tool registration + tests)
mcp = FastMCP("Qwen-Web") if FastMCP is not None else None

_container: McpContainer | None = None


def _get_mcp_app() -> Any:
    """Return FastMCP app instance or raise ImportError if mcp package is missing."""
    if mcp is None:
        raise ImportError(
            "The 'mcp' Python package is required to run the MCP server. Install it via 'pip install mcp'."
        )
    return mcp


def _register_tool(fn: Any) -> Any:
    """Register a function as an MCP tool if FastMCP is available.

    Returns the function unchanged when mcp is unavailable (graceful degradation).
    """
    if mcp is not None:
        return mcp.tool()(fn)
    return fn


def _isolate_thread_event_loop() -> None:
    """Ensure the worker thread has an isolated event loop for Playwright sync_api."""
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


def _tools() -> Any:
    """Return the MCP surface tool command, wiring the container once."""
    global _container
    from modules.mcp.src.surface_mcp_tool_command import McpToolCommand

    if _container is None:
        _container = McpContainer()
        _container.wire()
    return McpToolCommand(_container.core)


async def qwen_send_prompt(
    prompt: str,
    timeout_sec: int = 120,
    headless: bool = True,
) -> str:
    """Send a direct text prompt string to chat.qwen.ai and return AI answer."""
    return await asyncio.to_thread(_tools().send_prompt, prompt, timeout_sec, headless)


async def qwen_process_single(
    input_file: str,
    output_file: str | None = None,
    headless: bool = True,
) -> str:
    """Process a single Markdown prompt file (1:1 CLI Single File Mode)."""
    return await asyncio.to_thread(_tools().process_single, input_file, output_file, headless)


async def qwen_process_batch(
    input_dir: str | None = None,
    output_dir: str | None = None,
    headless: bool = True,
) -> str:
    """Process all prompt files inside an input directory (1:1 CLI Batch Mode)."""
    return await asyncio.to_thread(_tools().process_batch, input_dir, output_dir, headless)


async def qwen_start_watcher(interval_sec: int = 3, headless: bool = True) -> str:
    """Run folder watcher loop to continuously monitor input/ for new files."""
    return await asyncio.to_thread(_tools().start_watcher, interval_sec, headless)


async def qwen_setup_session() -> str:
    """Launch visible browser on chat.qwen.ai for manual login / session setup."""
    return await asyncio.to_thread(_tools().setup_session)


def qwen_get_audit_log(limit: int = 20) -> str:
    """Fetch latest entries from the JSONL audit trail log."""
    return _tools().get_audit_log(limit)


def _register_tools() -> None:
    """Register all 6 MCP tools on the FastMCP instance."""
    app = _get_mcp_app()
    tool: Callable[..., Callable[..., Any]] = app.tool

    tool()(qwen_send_prompt)
    tool()(qwen_process_single)
    tool()(qwen_process_batch)
    tool()(qwen_start_watcher)
    tool()(qwen_setup_session)
    tool()(qwen_get_audit_log)


def run_mcp_server() -> None:
    """Run the FastMCP server over stdio."""
    from modules.core.src.capabilities_observability import setup_observability

    setup_observability(DEFAULT_LOG)

    # Redirect standard text prints & logging to stderr to protect JSON-RPC stdio
    sys.stdout = sys.stderr

    app = _get_mcp_app()
    _register_tools()

    # Restore sys.stdout to sys.__stdout__ (FD 1) for FastMCP stdio transport
    sys.stdout = sys.__stdout__
    app.run()


def main() -> None:
    """Entry point for the qwen-web MCP server."""
    run_mcp_server()


if __name__ == "__main__":
    main()
