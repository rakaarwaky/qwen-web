# CLI Functional Requirements Document

## System Overview

The CLI surface (`modules/cli`) translates command-line arguments and interactive TTY inputs into `AppConfig` objects and delegates execution to the Core aggregate. It remains a **Smart Surface**: presentation, argument validation, dispatch, and lifecycle-boundary concerns belong here; business processing semantics remain in `modules/core`.

The authoritative Linux lifecycle owner is `modules/root_cli_main_entry.py`. The CLI root acquires the optional `LinuxGuard` before dispatch, emits systemd readiness after container initialization and lock acquisition, and emits shutdown plus releases the lock in a `finally` block. The MCP root is a separate lifecycle and constructs `SharedContainer(use_linux_guard=False)`.

## Functional Requirements

### FR-001: Argument Parsing & Config Building

The root parser reads `sys.argv` and constructs a validated `AppConfig` value object for run modes. Init is an action dispatched by the root and is not represented as an `AppConfig.mode`.

| Precedence | Signal | Result | Validation |
|---|---|---|---|
| 1 | `--login` | `mode="login"` | Input path is not required; manual login is always headed. |
| 2 | `init` subcommand or `--init` | Workspace initialization | Target directory is passed to the init surface. |
| 3 | `--watch` | `mode="watcher"` | `-i/--input` must be an existing directory. |
| 4 | No higher-priority signal and `input.is_dir()` | `mode="batch"` | Input must exist. |
| 5 | No higher-priority signal and `input.is_file()` | `mode="single"` | Input must exist. |

The effective precedence is therefore **`login > init > watch > is_dir()`**. If `--login` is combined with another action flag, login wins explicitly; if login is absent, init wins over watcher and path inference. An invalid run input is rejected with a non-success result and a clear diagnostic on `stderr`. Extensionless files are classified as single-file mode by filesystem type, never by filename suffix heuristics.

### FR-002: Interactive TUI Menu

The no-argument TTY fallback is owned by `InteractiveController`. The root calls the controller's production `run()` path after the menu selection, while the controller also retains a compatible combined prompt-and-run API for direct callers. Non-TTY input is rejected before prompting.

The menu supports Watcher, Batch, Single, Manual Login, Init, and Exit. The selected configuration is executed exactly once. The Login branch uses the shared `wait_for_login_confirmation()` callback from the login surface, so the ENTER boundary is not duplicated between interactive and explicit login flows.

### FR-003: Manual Login Orchestration

The login surface accepts an `AppConfig` and delegates session setup to the Core aggregate. It requires a TTY, forces headed mode at configuration construction, validates an existing session through the core, waits for the user to press ENTER while the browser remains open, and reports success only after the core verifies the authenticated chat UI.

The shared `wait_for_login_confirmation()` helper is the single owner of the user-facing login prompt. Authentication and session errors are returned through the standardized response envelope.

### FR-004: CLI LinuxGuard Lifecycle

The CLI root is the only production caller of LinuxGuard.

| Lifecycle point | Required behavior |
|---|---|
| Before dispatch | Acquire the non-blocking single-instance lock. A second instance returns a clear failure. |
| After container initialization and lock acquisition | Send `READY=1`; invalid or missing `NOTIFY_SOCKET` is non-fatal. |
| Normal completion or exception | Send `STOPPING=1`, then release the lock in `finally`. |
| MCP startup | Do not acquire a CLI lock or send CLI lifecycle notifications. |

No LinuxGuard logic is duplicated in the Core orchestrator. `SharedContainer` remains backward-compatible and exposes `linux=None` when `use_linux_guard=False`.

## API Contract

| Operation | Input | Output | Production caller |
|---|---|---|---|
| `_parse_args` | argv tokens | `argparse.Namespace` | `modules/root_cli_main_entry.py` |
| `_build_config` | parsed namespace | validated `AppConfig` | `modules/root_cli_main_entry.py` |
| `handle` (run) | args, core | response envelope | `modules/cli/src/surface_cli_run_command.py` |
| `handle` (login) | args, core, cfg | response envelope | `modules/cli/src/surface_cli_login_command.py` |
| `handle` (init) | args, core | response envelope | `modules/cli/src/surface_cli_init_command.py` |
| `InteractiveController.run` | optional config, prompt flag | response envelope | `modules/root_cli_main_entry.py` and direct surface callers |
| `_run_cli_lifecycle` | dispatch callback | process exit code | `modules/root_cli_main_entry.py` |

## Production File Map and Traceability

| Requirement / boundary | Production caller | Implementation file | Verification |
|---|---|---|---|
| CLI FR-001 parsing, precedence, and path validation | CLI root | `modules/root_cli_main_entry.py` | `tests/test_main_cli.py` |
| CLI FR-002 TTY menu and one execution path | CLI root and interactive surface | `modules/root_cli_main_entry.py`, `modules/cli/src/surface_cli_interactive_controller.py` | `tests/test_main_extended.py` |
| CLI FR-003 manual login and shared ENTER boundary | CLI root and login surface | `modules/cli/src/surface_cli_login_command.py` | `tests/test_login_session.py`, `tests/test_main_extended.py` |
| CLI init action | CLI root | `modules/cli/src/surface_cli_init_command.py` | `tests/test_main_cli.py`, `tests/test_init_cmd.py` |
| Linux lock and systemd notification capability | CLI lifecycle root | `modules/core/src/capabilities_linux_guard.py`, `modules/core/src/root_core_container.py` | `tests/test_linux.py`, `tests/test_cli_linux_guard.py` |
| MCP lock-free composition | MCP root | `modules/root_mcp_main_entry.py` | `tests/test_cli_linux_guard.py`, `tests/test_mcp_server*.py` |

## Integration Points

The CLI delegates processing and session orchestration to `modules/core`, uses shared `AppConfig` and error taxonomies from `modules/shared`, and uses `SharedContainer` for dependency composition. MCP remains a separate caller and does not enter the CLI lifecycle wrapper.

## Non-functional Requirements

The CLI must preserve standardized `stderr` diagnostics, avoid echoing credentials or sensitive session contents, and tolerate missing or invalid systemd notification sockets. Interactive prompts are available only on a TTY.

## Test Scenarios / QA Checklist

- [x] `--login` takes precedence over `--watch` and path inference.
- [x] `init` takes precedence over watcher and path inference when login is absent.
- [x] `--watch` requires an existing input directory.
- [x] Existing extensionless input files resolve to single-file mode.
- [x] Missing input paths return a non-success result with a `stderr` diagnostic.
- [x] No-argument TTY flow reaches `InteractiveController.run()` and executes the selected mode once.
- [x] Non-TTY execution rejects interactive prompts immediately.
- [x] Login and interactive login use one shared ENTER confirmation helper.
- [x] `init` creates `.qwen-web/` symlinks and `.gitignore` entries.
- [x] A second CLI instance using the same lock path fails immediately.
- [x] CLI lock cleanup occurs after normal completion and after exceptions.
- [x] CLI sends `READY=1` after successful initialization and `STOPPING=1` during shutdown.
- [x] Fake `NOTIFY_SOCKET` integration verifies notification ordering.
- [x] MCP constructs its container with `use_linux_guard=False` and remains lock-free.

## Assumptions & Constraints

The host OS supports POSIX terminal I/O, `fcntl.flock`, and Unix datagram sockets. Core processing semantics and MCP runtime implementation are outside this change set.

## References

- [Root PRD](../../PRD.md)
- [Core FRD](../core/FRD.md)
- Issues [#70](https://github.com/rakaarwaky/qwen-web/issues/70), [#71](https://github.com/rakaarwaky/qwen-web/issues/71), [#72](https://github.com/rakaarwaky/qwen-web/issues/72), and [#88](https://github.com/rakaarwaky/qwen-web/issues/88)
