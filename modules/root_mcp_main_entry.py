"""qwen-web MCP server entry point (MCP 2.0.0 API).

Root layer: bootstraps the MCP server over stdio using mcp.server.Server.
Tools are registered and delegate to the shared core aggregate.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, cast

from mcp.server import InitializationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    ContentBlock,
    ListResourcesResult,
    ListToolsResult,
    ReadResourceResult,
    TextContent,
    Tool,
)
from mcp_types._types import ServerCapabilities, ToolsCapability

from modules.core.src.capabilities_observability_setup import ObservabilitySetup
from modules.core.src.root_core_container import SharedContainer
from modules.mcp.src.surface_mcp_tool_command import McpToolCommand
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG

# ─── Logging setup ──────────────────────────────────────────────────────────

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("qwen-mcp")

# ─── Container & tool instance ──────────────────────────────────────────────

_container: McpToolCommand | None = None


def _get_tools() -> McpToolCommand:
    """Return the MCP surface tool command, wiring the container once."""
    global _container
    if _container is None:
        shared = SharedContainer()
        shared.wire()
        _container = McpToolCommand(shared.core)
    return _container


# ─── Async tool wrappers ────────────────────────────────────────────────────

# Map MCP tool names -> McpToolCommand method names
_TOOL_METHOD_MAP: dict[str, str] = {
    "qwen_send_prompt": "send_prompt",
    "qwen_process_single": "process_single",
    "qwen_process_batch": "process_batch",
    "qwen_start_watcher": "start_watcher",
    "qwen_setup_session": "setup_session",
    "qwen_get_audit_log": "get_audit_log",
}


def _async_tool(name: str) -> Callable[..., Awaitable[Sequence[str]]]:
    """Wrap a sync core method as an async MCP tool handler."""

    async def handler(*args: Any, **kwargs: Any) -> Sequence[str]:
        method_name = _TOOL_METHOD_MAP.get(name, name)

        def invoke() -> str:
            tools = _get_tools()
            return str(getattr(tools, method_name)(*args, **kwargs))

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, invoke)

    return handler


# ─── MCP Tool definitions ───────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="qwen_send_prompt",
        description="Send a direct text prompt string to chat.qwen.ai and return AI answer.",
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "timeout_sec": {"type": "integer", "default": 120},
                "headless": {"type": "boolean", "default": True},
            },
            "required": ["prompt"],
        },
    ),
    Tool(
        name="qwen_process_single",
        description="Process a single Markdown prompt file (1:1 CLI Single File Mode).",
        input_schema={
            "type": "object",
            "properties": {
                "input_file": {"type": "string"},
                "output_file": {"type": "string", "default": None},
                "headless": {"type": "boolean", "default": True},
            },
            "required": ["input_file"],
        },
    ),
    Tool(
        name="qwen_setup_session",
        description="Launch visible browser on chat.qwen.ai for manual login / session setup.",
        input_schema={"type": "object", "properties": {}},
    ),
    Tool(
        name="qwen_get_audit_log",
        description="Fetch latest entries from the JSONL audit trail log.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 20}},
        },
    ),
]

# Build async handlers for each tool — extract name from Tool objects
TOOL_HANDLERS: dict[str, Callable[..., Awaitable[Sequence[str]]]] = {
    tool.name: _async_tool(tool.name) for tool in TOOLS
}

# Async tool functions for direct surface calls
qwen_send_prompt = _async_tool("qwen_send_prompt")
qwen_process_single = _async_tool("qwen_process_single")
qwen_setup_session = _async_tool("qwen_setup_session")
qwen_get_audit_log = _async_tool("qwen_get_audit_log")

GENERATED_TOOLS = TOOL_HANDLERS

MCP_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "qwen_send_prompt",
        "method": "send_prompt",
        "doc": "Send a direct text prompt string to chat.qwen.ai and return AI answer.",
        "params": [("prompt", "str", True), ("timeout_sec", "int", False, 120), ("headless", "bool", False, True)],
    },
    {
        "name": "qwen_process_single",
        "method": "process_single",
        "doc": "Process a single Markdown prompt file (1:1 CLI Single File Mode).",
        "params": [("input_file", "str", True), ("output_file", "Any", False, None), ("headless", "bool", False, True)],
    },
    {
        "name": "qwen_setup_session",
        "method": "setup_session",
        "doc": "Launch visible browser on chat.qwen.ai for manual login / session setup.",
        "params": [],
    },
    {
        "name": "qwen_get_audit_log",
        "method": "get_audit_log",
        "doc": "Fetch latest entries from the JSONL audit trail log.",
        "params": [("limit", "int", False, 20)],
    },
]


async def _handle_list_tools() -> ListToolsResult:
    return ListToolsResult(tools=TOOLS)


async def _handle_call_tool(name: str, arguments: dict[str, Any] | None) -> CallToolResult:
    """Route tool calls to the appropriate handler."""
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise Exception(f"Unknown tool: {name}")

    try:
        result = await handler(**(arguments or {}))
        content_blocks: list[ContentBlock] = [TextContent(type="text", text=r) for r in result]
        return CallToolResult(content=content_blocks, is_error=False)
    except Exception as exc:
        log.error("Tool execution error: %s", exc)
        return CallToolResult(content=[], is_error=True)


async def _handle_list_resources() -> ListResourcesResult:
    """Return empty resource list."""
    return ListResourcesResult(resources=[])


async def _handle_read_resource(_uri: str) -> ReadResourceResult:
    """Return empty resource content."""
    return ReadResourceResult(contents=[])


# ─── Server runner ──────────────────────────────────────────────────────────


def run_mcp_server() -> None:
    """Run the MCP server over stdio."""
    ObservabilitySetup(DEFAULT_LOG).setup_observability()

    async def serve() -> None:
        async with stdio_server() as (read_stream, write_stream):
            capabilities = ServerCapabilities(tools=ToolsCapability())
            init_opts = InitializationOptions(
                server_name="Qwen-Web",
                server_version="4.1.0",
                capabilities=capabilities,
            )
            server = Server(
                name="Qwen-Web",
                version="4.1.0",
                on_list_tools=cast(Any, _handle_list_tools),
                on_call_tool=cast(Any, _handle_call_tool),
                on_list_resources=cast(Any, _handle_list_resources),
                on_read_resource=cast(Any, _handle_read_resource),
            )
            await server.run(read_stream, write_stream, initialization_options=init_opts)

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        log.info("MCP server shutting down")


def main() -> None:
    """Entry point for the qwen-web MCP server."""
    run_mcp_server()


if __name__ == "__main__":
    main()
