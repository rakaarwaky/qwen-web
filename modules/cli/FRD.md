# FRD — CLI Surface

## System Overview
The CLI surface (`modules/cli`) translates command-line arguments and interactive TTY inputs into `AppConfig` objects, delegating execution to the Core aggregate. It acts as a "Smart Surface" in the AES architecture, handling only presentation and boundary concerns without containing business logic.

## Functional Requirements

### FR-001: Argument Parsing & Config Building
- **Description**: Parses `sys.argv` and constructs a validated `AppConfig` Value Object.
- **Input**: CLI flags (`--watch`, `--headless`, `-i`, `-o`, etc.).
- **Output**: `AppConfig` instance.
- **Business Rules**: 
  - Must default to XDG-compliant paths if user paths are omitted.
  - Must infer `mode` (batch vs single) based on whether the input path is a directory or file.
- **Edge Cases**: Missing arguments, invalid directory paths, conflicting flags.
- **Error Handling**: Exits with code 1 and prints standardized error envelope to `stderr`.

### FR-002: Interactive TUI Menu
- **Description**: Provides a fallback interactive menu for users running the CLI without arguments.
- **Input**: TTY `stdin`.
- **Output**: `AppConfig` or `None` (exit).
- **Business Rules**: 
  - Must verify `sys.stdin.isatty()` before prompting.
  - Must allow selection of Watcher, Batch, Single, Login, or Init modes.
- **Edge Cases**: Piped input (non-TTY) must immediately reject interactive mode.
- **Error Handling**: Returns error envelope if TTY check fails.

### FR-003: Manual Login Orchestration
- **Description**: Orchestrates the visible browser login flow.
- **Input**: `AppConfig` (headless=False).
- **Output**: Success/Failure envelope.
- **Business Rules**: 
  - Must force `headless=False`.
  - Must block execution and wait for user `ENTER` keypress after browser opens.
- **Edge Cases**: User closes browser before pressing ENTER.
- **Error Handling**: Catches `AuthRequiredError` and prompts user to retry.

## API Contract

| Operation | Input | Output | Description |
|-----------|-------|--------|-------------|
| `handle` (run) | `args`, `core` | `dict` | Dispatches processing based on `AppConfig.mode`. |
| `handle` (login) | `args`, `core`, `cfg` | `dict` | Runs manual login flow. |
| `handle` (init) | `args`, `core` | `dict` | Provisions workspace directories. |

## Integration Points
- **Internal**: `modules/core` (CoreOrchestrator aggregate), `modules/shared` (Taxonomy VOs).

## Non-functional Requirements (Detailed)
- **Usability**: Must support ANSI colors for TUI menus when attached to a TTY.
- **Security**: Must never echo sensitive session paths or credentials to stdout.

## Test Scenarios / QA Checklist
- [ ] Verify `--watch` flag correctly sets `AppConfig.mode` to "watcher".
- [ ] Verify non-TTY execution immediately rejects interactive prompts.
- [ ] Verify `init` command creates `.qwen-web/` symlinks and `.gitignore` entries.

## Assumptions & Constraints
- Assumes the host OS supports standard POSIX terminal I/O.

## Reference
- PRD: [Root PRD.md](../../PRD.md)
