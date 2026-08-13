# FRD — Core Automation Engine

## System Overview
The Core module (`modules/core`) is the heart of the qwen-web automation engine. It implements the AES Capabilities and Agent layers, orchestrating the Playwright browser lifecycle, DOM interaction, stream monitoring, and file system routing. It exposes the `ICoreAggregate` contract to the Surface layers (CLI/MCP), ensuring that business logic remains completely isolated from user-facing boundaries.

## Functional Requirements

### FR-001: Browser Session Management
- **Description**: Manages the Chromium browser lifecycle, persistent profiles, and network optimization.
- **Input**: `AppConfig` (session path, headless flag, viewport).
- **Output**: Active `BrowserContext` and `Page`.
- **Business Rules**: 
  - Must use `launch_persistent_context` to retain cookies/LocalStorage.
  - Must clean stale Chromium lock files (`SingletonLock`) before launch.
  - Must block media/font/image routes to reduce network overhead.
- **Edge Cases**: Stale profile directories, missing execute permissions on profile folders, concurrent instance lock collisions.
- **Error Handling**: Raises `BrowserLaunchError` if context fails to initialize after 3 retries. Raises `AuthRequiredError` if redirected to a login page.

### FR-002: Prompt Injection
- **Description**: Injects text into the Qwen Web UI input field.
- **Input**: `Page`, `PromptText`.
- **Output**: None (mutates DOM state).
- **Business Rules**: 
  - Must attempt 3 tiers of injection sequentially: 1) React value setter + synthetic events, 2) ContentEditable `innerText` setter, 3) Playwright `fill()`/`type()`.
- **Edge Cases**: UI changes, hidden input fields, React state synchronization delays.
- **Error Handling**: Raises `PromptInjectionError` if all 3 tiers fail or if post-injection verification fails.

### FR-003: Stream Monitoring & Stability
- **Description**: Polls the DOM to detect when the AI has finished generating a response.
- **Input**: `Page`, `TimeoutSec`, `MessageCount` (baseline).
- **Output**: `ResponseText`.
- **Business Rules**: 
  - Must poll at configurable intervals (default 1.0s).
  - Must wait for the text to remain unchanged for N consecutive checks (default 4).
  - Must verify generation is complete by checking for the absence of "Stop" or "Typing" indicators.
- **Edge Cases**: Network drops during generation, UI noise (e.g., "Qwen3" model tags) in the extracted text.
- **Error Handling**: Raises `NetworkTimeoutError` on Playwright IPC failures. Raises `OutputValidationError` if the final text contains CAPTCHA or server error keywords.

### FR-004: File Pipeline Orchestration
- **Description**: Routes files through the processing queue (input -> processing -> done/failed).
- **Input**: Directory paths, `AppConfig`.
- **Output**: Processed files moved to target directories.
- **Business Rules**: 
  - Must use atomic file moves to prevent data loss.
  - Must support role-based path resolution (e.g., `role-coder/`, `role-writer/`).
  - Must integrate with the Circuit Breaker to halt processing if consecutive failures exceed the threshold.
- **Edge Cases**: File permission errors, disk full, concurrent watcher instances.
- **Error Handling**: Quarantines failed files to the `failed/` directory and logs the stack trace to `errors.jsonl`.

## API Contract

| Operation | Input | Output | Description |
|-----------|-------|--------|-------------|
| `process_single_file` | `input_file`, `output_file`, `headless` | `ResponseText` | Processes one file end-to-end. |
| `process_batch` | `input_dir`, `output_dir`, `headless` | `ResponseText` | Processes all files in a directory. |
| `process_watcher` | `interval_sec`, `headless` | `ResponseText` | Runs the continuous polling loop. |
| `send_prompt` | `prompt`, `timeout_sec`, `headless` | `ResponseText` | Sends raw text without file I/O. |
| `setup_session` | None | `ResponseText` | Opens headed browser for manual login. |

## Integration Points
- **3rd Party**: Playwright (Browser automation), structlog/Sentry/OpenTelemetry (Observability).
- **Internal**: `modules/shared` (Taxonomy VOs, Contracts, Utility functions).

## Non-functional Requirements (Detailed)
- **Performance**: DOM polling must not block the main thread for >300ms per cycle.
- **Security**: Session directories must have `0o700` permissions. No credentials logged to stdout.
- **SLA**: Watcher mode must respond to `SIGINT`/`SIGTERM` within 1 second to ensure graceful systemd shutdowns.

## Test Scenarios / QA Checklist
- [ ] Verify atomic move prevents file loss when process is killed during I/O.
- [ ] Verify `AuthRequiredError` is raised when session cookies expire.
- [ ] Verify Circuit Breaker trips after N consecutive failures and halts the batch.
- [ ] Verify CAPTCHA keywords in AI response trigger `OutputValidationError`.

## Assumptions & Constraints
- Assumes the user has a valid Chromium/Chrome binary installed on the Linux host.
- Constrained by Playwright's synchronous API limitations (requires thread-isolated event loops).

## Glossary
- **AES**: Agentic Engineering System (the 7-layer architecture).
- **XDG**: XDG Base Directory Specification for Linux file paths.

## Reference
- PRD: [Root PRD.md](../../PRD.md)
