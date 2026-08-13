# FRD — MCP Surface

## System Overview
The MCP surface (`modules/mcp`) exposes the Core aggregate as a Model Context Protocol (MCP) server over stdio. It allows local AI agents (like Claude Desktop, Cursor, or custom agentic workflows) to invoke qwen-web capabilities as standardized tools without managing browser lifecycles or DOM selectors.

## Functional Requirements

### FR-001: Tool Registration & Specification
- **Description**: Registers core functionalities as MCP tools using the FastMCP framework.
- **Input**: `MCP_TOOL_SPECS` definition table.
- **Output**: Registered FastMCP tool handlers.
- **Business Rules**: 
  - Must map 1:1 with CLI capabilities (`qwen_send_prompt`, `qwen_process_single`, etc.).
  - Must define strict type hints for all tool parameters.
- **Edge Cases**: Missing `mcp` Python package dependency.
- **Error Handling**: Gracefully degrades (skips registration) if FastMCP is unavailable, allowing the module to be imported for testing.

### FR-002: Async Execution & Threading
- **Description**: Bridges the synchronous Playwright Core aggregate with the asynchronous MCP stdio transport.
- **Input**: Async tool invocation.
- **Output**: Stringified `ResponseText`.
- **Business Rules**: 
  - Must use `asyncio.to_thread` to offload synchronous Playwright calls to a worker thread.
  - Must isolate the thread's event loop to prevent Playwright sync_api collisions.
- **Edge Cases**: Thread starvation, event loop closure during shutdown.
- **Error Handling**: Catches thread exceptions and returns standardized MCP error payloads.

### FR-003: Stdio Transport Protection
- **Description**: Protects the JSON-RPC stdio stream from accidental stdout pollution.
- **Input**: Application bootstrap.
- **Output**: Clean stdio transport.
- **Business Rules**: 
  - Must redirect `sys.stdout` to `sys.stderr` during tool execution.
  - Must restore `sys.__stdout__` before starting the FastMCP app loop.
- **Edge Cases**: Third-party libraries printing directly to stdout.
- **Error Handling**: Ensures `sys.stdout` is restored in a `finally` block to prevent transport corruption.

## API Contract

| Operation | Input | Output | Description |
|-----------|-------|--------|-------------|
| `qwen_send_prompt` | `prompt`, `timeout_sec`, `headless` | `str` | Sends raw text prompt. |
| `qwen_process_single` | `input_file`, `output_file`, `headless` | `str` | Processes one markdown file. |
| `qwen_process_batch` | `input_dir`, `output_dir`, `headless` | `str` | Processes a directory. |
| `qwen_start_watcher` | `interval_sec`, `headless` | `str` | Starts the continuous watcher. |
| `qwen_setup_session` | None | `str` | Validates an existing session or waits for visible browser login to complete. |
| `qwen_get_audit_log` | `limit` | `str` | Fetches JSONL audit entries. |

## Integration Points
- **3rd Party**: FastMCP (MCP framework), asyncio (Event loop management).
- **Internal**: `modules/core` (CoreOrchestrator aggregate).

## Non-functional Requirements (Detailed)
- **Performance**: Tool invocation overhead (thread dispatch) must be <50ms.
- **Security**: Must never leak stdio transport by printing raw Python tracebacks to stdout.

## Test Scenarios / QA Checklist
- [ ] Verify `asyncio.to_thread` successfully executes synchronous Playwright calls.
- [ ] Verify `sys.stdout` redirection prevents JSON-RPC parsing errors.
- [ ] Verify tool registration fails gracefully if `mcp` package is missing.

## Assumptions & Constraints
- Assumes the MCP client (e.g., AI Agent) supports the standard MCP stdio transport.
- Constrained by Python's GIL; heavy DOM polling in the worker thread may block other async MCP tasks.

## Reference
- PRD: [Root PRD.md](../../PRD.md)
