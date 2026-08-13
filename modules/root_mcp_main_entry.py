#!/usr/bin/env python3
"""qwen-web MCP server entry point.

Root layer: bootstraps the FastMCP server over stdio with the wired MCP
container. The 6 tools are generated from a specification table and
registered on the FastMCP instance, delegating to the shared core aggregate.
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

from modules.core.src.root_core_container import SharedContainer
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG

# ─── MCP tool specification table ────────────────────────────────────────

MCP_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "qwen_send_prompt",
        "method": "send_prompt",
        "doc": "Send a direct text prompt string to chat.qwen.ai and return AI answer.",
        "params": [
            ("prompt", "str", True),
            ("timeout_sec", "int", False, 120),
            ("headless", "bool", False, True),
        ],
    },
    {
        "name": "qwen_process_single",
        "method": "process_single",
        "doc": "Process a single Markdown prompt file (1:1 CLI Single File Mode).",
        "params": [
            ("input_file", "str", True),
            ("output_file", "str | None", False, None),
            ("headless", "bool", False, True),
        ],
    },
    {
        "name": "qwen_process_batch",
        "method": "process_batch",
        "doc": "Process all prompt files inside an input directory (1:1 CLI Batch Mode).",
        "params": [
            ("input_dir", "str | None", False, None),
            ("output_dir", "str | None", False, None),
            ("headless", "bool", False, True),
        ],
    },
    {
        "name": "qwen_start_watcher",
        "method": "start_watcher",
        "doc": "Run folder watcher loop to continuously monitor input/ for new files.",
        "params": [
            ("interval_sec", "int", False, 3),
            ("headless", "bool", False, True),
        ],
    },
    {
        "name": "qwen_setup_session",
        "method": "setup_session",
        "doc": "Launch visible browser on chat.qwen.ai for manual login / session setup.",
        "params": [],
    },
]

# FastMCP application instance (module-level for tool registration + tests)
mcp = FastMCP("Qwen-Web") if FastMCP is not None else None

_container: SharedContainer | None = None


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


def _tools() -> Any:
    """Return the MCP surface tool command, wiring the container once."""
    global _container
    from modules.mcp.src.surface_mcp_tool_command import McpToolCommand

    if _container is None:
        _container = SharedContainer(use_linux_guard=False)
        _container.wire()
    return McpToolCommand(_container.core)


def _async_tool(name: str) -> Callable[..., Any]:
    """Create an async MCP tool that delegates to a sync core method via asyncio.to_thread.

    Eliminates the duplicated await asyncio.to_thread(_tools().method_name, ...) pattern.
    """

    async def handler(*args: Any, **kwargs: Any) -> str:
        return await asyncio.to_thread(getattr(_tools(), name), *args, **kwargs)

    return handler


def _make_async_tool(spec: dict[str, Any]) -> Callable[..., Any]:
    """Generate an async MCP tool function from a spec entry.

    Each spec defines the core method name, docstring, and parameter metadata.
    The generated function delegates to _async_tool(spec["method"]).
    """
    handler = _async_tool(spec["method"])
    handler.__name__ = spec["name"]
    handler.__doc__ = spec["doc"]
    return handler


# Generate async tool functions from specification table
GENERATED_TOOLS: dict[str, Callable[..., Any]] = {
    _spec["name"]: _make_async_tool(_spec) for _spec in MCP_TOOL_SPECS
}


def qwen_get_audit_log(limit: int = 20) -> str:
    """Fetch latest entries from the JSONL audit trail log."""
    return str(_tools().get_audit_log(limit))


def _register_tools() -> None:
    """Register all MCP tools on the FastMCP instance."""
    app = _get_mcp_app()
    tool: Callable[..., Callable[..., Any]] = app.tool

    for spec in MCP_TOOL_SPECS:
        tool()(GENERATED_TOOLS[spec["name"]])

    tool()(qwen_get_audit_log)


def run_mcp_server() -> None:
    """Run the FastMCP server over stdio."""
    from modules.core.src.capabilities_observability_setup import ObservabilitySetup

    ObservabilitySetup(DEFAULT_LOG).setup_observability()

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
