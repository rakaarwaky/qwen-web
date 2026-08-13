# MCP Functional Requirements Document

## System Overview

The MCP surface (`modules/mcp`) exposes the Core aggregate as a Model Context Protocol (MCP) server over stdio. It allows local AI agents such as Claude Desktop, Cursor, or custom agentic workflows to invoke qwen-web capabilities as standardized tools without managing browser lifecycles or DOM selectors.

## Functional Requirements

### FR-001: Declarative Tool Registration and Specification

- **Description**: Registers all MCP capabilities as FastMCP tools from the `MCP_TOOL_SPECS` table.
- **Input**: A specification entry containing the public tool name, core method name, documentation, and parameter metadata.
- **Output**: One generated async FastMCP handler per specification entry.
- **Business Rules**:
  - The specification table is the single source of truth for MCP registration.
  - The table must map one-to-one with the exposed capabilities: `qwen_send_prompt`, `qwen_process_single`, `qwen_process_batch`, `qwen_start_watcher`, `qwen_setup_session`, and `qwen_get_audit_log`.
  - Each parameter must declare a supported type and, when optional, its default value.
  - `qwen_get_audit_log` is declaratively specified with `limit: int = 20`; it must not have a separate manual registration path.
  - Generated handlers expose the specification-derived name, docstring, annotations, and `inspect.Signature` so FastMCP can build the client-facing schema.
- **Edge Cases**: Missing `mcp` Python package dependency.
- **Error Handling**: The module remains importable for tests when FastMCP is unavailable; server startup raises a clear `ImportError` if the app is requested.

### FR-002: Async Execution and Threading

- **Description**: Bridges the synchronous Playwright Core aggregate with the asynchronous MCP stdio transport.
- **Input**: Async tool invocation.
- **Output**: Stringified `ResponseText`.
- **Business Rules**:
  - Every generated handler delegates synchronous core work through `asyncio.to_thread`.
  - The worker-local execution context is marked while the core method runs, including its `print` output.
  - The worker context is reset in a `finally` block even when the core method raises.
- **Edge Cases**: Thread starvation and event-loop closure during shutdown.
- **Error Handling**: Exceptions raised by the synchronous core method propagate through the async handler for FastMCP to report according to its normal error handling.

### FR-003: Stdio Transport Protection

- **Description**: Protects the JSON-RPC stdio stream from accidental stdout pollution during tool execution without suppressing FastMCP transport messages.
- **Input**: MCP server bootstrap and tool execution.
- **Output**: JSON-RPC transport remains on stdout; tool diagnostics are routed to stderr.
- **Business Rules**:
  - `run_mcp_server()` installs a proxy around the existing `sys.stdout` only for the lifetime of the server.
  - Writes made while a generated tool is executing are sent to `sys.stderr` through a context-local execution flag.
  - Writes made by FastMCP outside tool execution continue to use the original stdout stream.
  - The previous stdout object is restored in a `finally` block when the server exits.
- **Edge Cases**: Third-party libraries printing through `sys.stdout`, nested tool calls, and server shutdown after a tool exception.
- **Error Handling**: Restoration of stdout is guaranteed even when registration or the FastMCP app loop raises.

## API Contract

| Operation | Input | Output | Description |
|-----------|-------|--------|-------------|
| `qwen_send_prompt` | `prompt`, `timeout_sec=120`, `headless=True` | `str` | Sends raw text prompt. |
| `qwen_process_single` | `input_file`, `output_file=None`, `headless=True` | `str` | Processes one Markdown file. |
| `qwen_process_batch` | `input_dir=None`, `output_dir=None`, `headless=True` | `str` | Processes a directory. |
| `qwen_start_watcher` | `interval_sec=3`, `headless=True` | `str` | Starts the continuous watcher. |
| `qwen_setup_session` | None | `str` | Validates an existing session or waits for visible browser login to complete. |
| `qwen_get_audit_log` | `limit=20` | `str` | Fetches JSONL audit entries. |

## MCP File Map

| File | Responsibility |
|------|----------------|
| `modules/root_mcp_main_entry.py` | FastMCP application bootstrap, `MCP_TOOL_SPECS`, generated async handlers, declarative registration, and stdout isolation. |
| `modules/mcp/src/surface_mcp_tool_command.py` | MCP surface adapter that maps generated tool calls to the `ICoreAggregate` contract. |
| `modules/shared/src/contract_core_aggregate.py` | Shared core interface, including the existing `get_audit_log(limit=20)` contract. |
| `modules/core/src/agent_core_orchestrator.py` | Concrete core aggregate delegation; out of scope for issues #73–#75. |
| `modules/core/src/capabilities_audit_repository.py` | Audit JSONL persistence and retrieval; unchanged for issues #73–#75. |
| `tests/test_mcp_server.py` | Basic generated-tool and audit-log behavior tests. |
| `tests/test_mcp_server_async.py` | Async wrapper and audit-log response tests. |
| `tests/test_mcp_server_extended.py` | Registration-table, signature, server lifecycle, and stdout-isolation tests. |

## Integration Points

- **Third Party**: FastMCP (MCP framework) and `asyncio` (event-loop and worker-thread management).
- **Internal**: `modules/core` (CoreOrchestrator aggregate), `modules/shared` (aggregate contract), and the MCP surface adapter.

## Non-functional Requirements

- **Performance**: Tool invocation overhead from thread dispatch should remain below 50 ms excluding browser work.
- **Security and Integrity**: The server must never leak raw Python diagnostics or tracebacks into the JSON-RPC stdout stream.
- **Scope Constraint**: `AuditRepository.get_audit_log()` and `LinuxGuard` are not modified for issues #73–#75. Any future contract change must be coordinated with the owning implementation work.

## Test Scenarios / QA Checklist

- [ ] Verify every `MCP_TOOL_SPECS` entry produces exactly one generated handler.
- [ ] Verify `qwen_get_audit_log` is present in `MCP_TOOL_SPECS`, uses the common generator, and has default `limit=20`.
- [ ] Verify the async wrapper dispatches synchronous core calls through `asyncio.to_thread`.
- [ ] Verify the audit-log handler returns the expected missing-file and JSON response strings.
- [ ] Verify tool execution output is absent from JSON-RPC stdout while FastMCP transport output remains on stdout.
- [ ] Verify stdout is restored after server shutdown or startup failure.
- [ ] Verify tool registration fails clearly when the `mcp` package is unavailable.
- [ ] Run `pytest`.
- [ ] Run `ruff format --check modules/ tests/`.
- [ ] Run `ruff check modules/ tests/`.
- [ ] Run `mypy modules/`.

## Assumptions and Constraints

- The MCP client, such as an AI agent using the standard MCP stdio transport, owns the JSON-RPC protocol stream.
- The synchronous browser automation remains delegated to worker threads; the Python GIL may limit concurrency for CPU-heavy work.
- The audit repository contract and LinuxGuard implementation are outside the scope of this change.

## Reference

- PRD: [Root PRD.md](../../PRD.md)
