"""qwen-web MCP server entry point.

Root layer: bootstraps the FastMCP server over stdio with the wired MCP
container. The tools are generated from a specification table and registered
on the FastMCP instance, delegating to the shared core aggregate.
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import sys
from collections.abc import Callable
from typing import Any, TextIO, cast

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
    {
        "name": "qwen_get_audit_log",
        "method": "get_audit_log",
        "doc": "Fetch latest entries from the JSONL audit trail log.",
        "params": [("limit", "int", False, 20)],
    },
]

# FastMCP application instance (module-level for tool registration + tests)
mcp = FastMCP("Qwen-Web") if FastMCP is not None else None

_container: SharedContainer | None = None
_tool_execution: contextvars.ContextVar[bool] = contextvars.ContextVar("mcp_tool_execution", default=False)


class _McpBufferProxy:
    """Binary buffer proxy that routes writes to the active execution-context stream."""

    def __init__(self, transport_buffer: Any, diagnostics_buffer: Any) -> None:
        self._transport_buffer = transport_buffer
        self._diagnostics_buffer = diagnostics_buffer

    def write(self, data: bytes) -> int:
        target = self._diagnostics_buffer if _tool_execution.get() else self._transport_buffer
        return int(target.write(data))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._transport_buffer, name)


class _McpStdoutProxy:
    """Keep FastMCP transport writes on stdout and tool diagnostics on stderr.

    FastMCP owns the process stdout stream for JSON-RPC messages. Synchronous
    core calls run in ``asyncio.to_thread`` workers, so a context-local flag can
    route ordinary ``print`` calls made by a tool to stderr without redirecting
    FastMCP's own transport output.
    """

    def __init__(self, transport: TextIO, diagnostics: TextIO) -> None:
        self._transport = transport
        self._diagnostics = diagnostics

    def write(self, text: str) -> int:
        target = self._diagnostics if _tool_execution.get() else self._transport
        return target.write(text)

    def writelines(self, lines: list[str]) -> None:
        target = self._diagnostics if _tool_execution.get() else self._transport
        target.writelines(lines)

    def flush(self) -> None:
        self._transport.flush()
        self._diagnostics.flush()

    @property
    def buffer(self) -> Any:
        """Return a binary buffer proxy that routes writes to the active context stream."""
        return _McpBufferProxy(self._transport.buffer, self._diagnostics.buffer)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._transport, name)


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
    """Create an async MCP tool that delegates to a sync core method.

    The complete lookup and invocation happen inside ``asyncio.to_thread`` so
    any output produced while a tool executes carries the tool context and is
    routed away from the JSON-RPC stdout stream.
    """

    async def handler(*args: Any, **kwargs: Any) -> str:
        def invoke() -> str:
            token = _tool_execution.set(True)
            try:
                return str(getattr(_tools(), name)(*args, **kwargs))
            finally:
                _tool_execution.reset(token)

        return await asyncio.to_thread(invoke)

    return handler


_TYPE_ANNOTATIONS: dict[str, object] = {
    "str": str,
    "int": int,
    "bool": bool,
    "str | None": str | None,
}


def _make_async_tool(spec: dict[str, Any]) -> Callable[..., Any]:
    """Generate an async MCP tool function, including its public signature."""
    handler: Any = _async_tool(spec["method"])
    parameters: list[inspect.Parameter] = []
    annotations: dict[str, object] = {"return": str}

    for param in spec["params"]:
        name, type_name, required, *default_values = param
        if type_name not in _TYPE_ANNOTATIONS:
            raise ValueError(f"Unsupported MCP parameter type: {type_name}")
        if required:
            default = inspect.Parameter.empty
        else:
            default = default_values[0] if default_values else None
        parameters.append(
            inspect.Parameter(
                name=name,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=default,
                annotation=_TYPE_ANNOTATIONS[type_name],
            )
        )
        annotations[name] = _TYPE_ANNOTATIONS[type_name]

    handler.__name__ = spec["name"]
    handler.__doc__ = spec["doc"]
    handler.__annotations__ = annotations
    handler.__signature__ = inspect.Signature(parameters=parameters, return_annotation=str)
    return cast(Callable[..., Any], handler)


# Generate async tool functions from specification table.
GENERATED_TOOLS: dict[str, Callable[..., Any]] = {_spec["name"]: _make_async_tool(_spec) for _spec in MCP_TOOL_SPECS}

# Expose generated tools as module-level callables for registration and tests.
# Keys originate from the in-code MCP_TOOL_SPECS literal, not external input.
globals().update(GENERATED_TOOLS)


def _register_tools() -> None:
    """Register every MCP tool generated from ``MCP_TOOL_SPECS`` exactly once."""
    app = _get_mcp_app()
    for spec in MCP_TOOL_SPECS:
        app.tool()(GENERATED_TOOLS[spec["name"]])


def run_mcp_server() -> None:
    """Run the FastMCP server over stdio without polluting JSON-RPC stdout."""
    from modules.core.src.capabilities_observability_setup import ObservabilitySetup

    ObservabilitySetup(DEFAULT_LOG).setup_observability()

    app = _get_mcp_app()
    previous_stdout = sys.stdout
    sys.stdout = _McpStdoutProxy(cast(TextIO, previous_stdout), cast(TextIO, sys.stderr))
    try:
        _register_tools()
        app.run()
    finally:
        sys.stdout = previous_stdout


def main() -> None:
    """Entry point for the qwen-web MCP server."""
    run_mcp_server()


if __name__ == "__main__":
    main()
