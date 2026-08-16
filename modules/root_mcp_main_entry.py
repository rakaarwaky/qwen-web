"""qwen-web MCP server entry point (MCP 2.0.0 API).

Root layer: bootstraps the MCP server over stdio using mcp.server.Server.
Tools are registered and delegate to the shared core aggregate.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from mcp.server import InitializationOptions, Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from mcp.types import TextContent, Tool
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
        _container = McpToolCommand(
            direct=shared.agent_direct_prompt_orchestrator,
            file_only=shared.agent_prompt_file_orchestrator,
            attachment=shared.agent_attachment_prompt_orchestrator,
            session=shared.agent_session_orchestrator,
            setup=shared.agent_setup_orchestrator,
            workspace=shared.workspace,
        )
    return _container


# ─── Async tool wrappers ────────────────────────────────────────────────────

# Map MCP tool names -> McpToolCommand method names
_TOOL_METHOD_MAP: dict[str, str] = {
    "process_direct_prompt": "process_direct_prompt",
    "process_prompt_file_only": "process_prompt_file_only",
    "process_prompt_with_attachment": "process_prompt_with_attachment",
    "check_session": "check_session",
    "delete_session": "delete_session",
    "setup_session": "setup_session",
    "init": "init_workspace",
    "init_workspace": "init_workspace",
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
        name="init",
        description="Initialize workspace directory structure, .agents/skills/qwen-web/SKILL.md guide, sample prompt/file, and .gitignore.",
        input_schema={
            "type": "object",
            "properties": {
                "target_dir": {"type": "string", "default": "."},
            },
        },
    ),
    Tool(
        name="process_direct_prompt",
        description="Process a direct text prompt string to chat.qwen.ai and return the AI answer.",
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
        name="process_prompt_file_only",
        description="Process a single Markdown prompt file (no attachment) on chat.qwen.ai.",
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
        name="process_prompt_with_attachment",
        description="Process a Markdown prompt file with a document attachment on chat.qwen.ai.",
        input_schema={
            "type": "object",
            "properties": {
                "prompt_file": {"type": "string"},
                "attachment_file": {"type": "string"},
                "output_file": {"type": "string", "default": None},
                "headless": {"type": "boolean", "default": True},
            },
            "required": ["prompt_file", "attachment_file"],
        },
    ),
    Tool(
        name="check_session",
        description="Check status and validity of saved browser session tokens.",
        input_schema={"type": "object", "properties": {}},
    ),
    Tool(
        name="delete_session",
        description="Delete saved browser session tokens. Requires confirm=True parameter.",
        input_schema={
            "type": "object",
            "properties": {
                "confirm": {"type": "boolean", "default": False},
            },
        },
    ),
    Tool(
        name="setup_session",
        description="Launch visible browser on chat.qwen.ai for manual login / session setup.",
        input_schema={"type": "object", "properties": {}},
    ),
]

# Build async handlers for each tool — extract name from Tool objects
TOOL_HANDLERS: dict[str, Callable[..., Awaitable[Sequence[str]]]] = {
    tool.name: _async_tool(tool.name) for tool in TOOLS
}

# Async tool functions for direct surface calls
init = _async_tool("init")
process_direct_prompt = _async_tool("process_direct_prompt")
process_prompt_file_only = _async_tool("process_prompt_file_only")
process_prompt_with_attachment = _async_tool("process_prompt_with_attachment")
check_session = _async_tool("check_session")
delete_session = _async_tool("delete_session")
setup_session = _async_tool("setup_session")

GENERATED_TOOLS = TOOL_HANDLERS

MCP_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "process_direct_prompt",
        "method": "process_direct_prompt",
        "doc": "Process a direct text prompt string to chat.qwen.ai and return the AI answer.",
        "params": [("prompt", "str", True), ("timeout_sec", "int", False, 120), ("headless", "bool", False, True)],
    },
    {
        "name": "process_prompt_file_only",
        "method": "process_prompt_file_only",
        "doc": "Process a single Markdown prompt file (no attachment) on chat.qwen.ai.",
        "params": [("input_file", "str", True), ("output_file", "Any", False, None), ("headless", "bool", False, True)],
    },
    {
        "name": "process_prompt_with_attachment",
        "method": "process_prompt_with_attachment",
        "doc": "Process a Markdown prompt file with a document attachment on chat.qwen.ai.",
        "params": [
            ("prompt_file", "str", True),
            ("attachment_file", "str", True),
            ("output_file", "Any", False, None),
            ("headless", "bool", False, True),
        ],
    },
    {
        "name": "setup_session",
        "method": "setup_session",
        "doc": "Launch visible browser on chat.qwen.ai for manual login / session setup.",
        "params": [],
    },
]


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
            server = Server("Qwen-Web")

            async def handle_list_tools(
                context: Any, params: types.PaginatedRequestParams | None = None
            ) -> types.ListToolsResult:
                return types.ListToolsResult(tools=TOOLS)

            async def handle_call_tool(
                context: Any, params: types.CallToolRequestParams
            ) -> types.CallToolResult:
                handler = TOOL_HANDLERS.get(params.name)
                if handler is None:
                    raise ValueError(f"Unknown tool: {params.name}")
                try:
                    result = await handler(**(params.arguments or {}))
                    if isinstance(result, str):
                        content_blocks: list[types.TextContent] = [
                            types.TextContent(type="text", text=result)
                        ]
                    else:
                        content_blocks = [
                            types.TextContent(type="text", text=str(r)) for r in result
                        ]
                    return types.CallToolResult(content=content_blocks, is_error=False)
                except Exception as exc:
                    log.error("Tool execution error: %s", exc)
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=f"Error: {exc}")],
                        is_error=True,
                    )

            async def handle_list_resources(
                context: Any, params: types.PaginatedRequestParams | None = None
            ) -> types.ListResourcesResult:
                return types.ListResourcesResult(resources=[])

            async def handle_read_resource(
                context: Any, params: types.ReadResourceRequestParams
            ) -> types.ReadResourceResult:
                return types.ReadResourceResult(contents=[])

            server.add_request_handler("tools/list", types.PaginatedRequestParams, handle_list_tools)
            server.add_request_handler("tools/call", types.CallToolRequestParams, handle_call_tool)
            server.add_request_handler("resources/list", types.PaginatedRequestParams, handle_list_resources)
            server.add_request_handler("resources/read", types.ReadResourceRequestParams, handle_read_resource)

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
