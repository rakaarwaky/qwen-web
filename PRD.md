# Product Requirements Document (PRD)
## Qwen AI Web Automation CLI (`qwen-web`)

---

### 1. Overview & Vision

`qwen-web` is a production-grade, resilient CLI automation tool and MCP Server that interacts with the Qwen AI web interface (`chat.qwen.ai`) without requiring official API keys. It enables batch prompt processing, real-time file watching, persistent session management, 1:1 MCP Server tool integration for local AI agents, structured observability (structlog + OpenTelemetry + Sentry), and JSONL audit logging via Playwright browser automation.

---

### 2. Architecture & Module Layout

| Module | Responsibility |
| :--- | :--- |
| `src/main.py` | CLI entrypoint, argument parser, interactive TUI menu, MCP launcher |
| `src/mcp_server.py` | MCP Server entrypoint exposing 1:1 CLI features as Model Context Protocol tools |
| `src/types.py` | Type definitions, AppConfig dataclass, custom exceptions, CircuitBreaker, RateLimiter, LifecycleEmitter |
| `src/browser.py` | Playwright `launch_persistent_context` lifecycle management, session health checks |
| `src/qwen_client.py` | Core automation orchestrator: prompt injection, response polling, file upload |
| `src/prompt_injector.py` | DOM text injection via React prototype setter + clipboard fallback |
| `src/sender.py` | Send button click logic, message counting, latest message extraction |
| `src/streamer.py` | Response streaming detection, stability checks, output validation (CAPTCHA/error pages) |
| `src/saver.py` | Output file writing with metadata traceability header and JSON sidecar |
| `src/file_uploader.py` | File attachment upload via Playwright file chooser |
| `src/pipeline.py` | File pipeline: watcher loop, batch processor, single file handler, retry logic, AuditLog |
| `src/observability.py` | `structlog` setup, OpenTelemetry tracing, Sentry SDK initialization, span helpers |

---

### 3. Core Operating Modes

#### 3.1 Interactive Terminal UI (TUI) Mode
- **Trigger**: Script executed without CLI arguments.
- **Features**:
  - Selection menu: Watcher, Batch, Single File, Manual Login, Init, Exit.
  - Prompts for headless vs. headed browser mode.
  - Graceful keyboard interrupt handling (`Ctrl+C`).
  - Returns `None` on exit/init choices (no `sys.exit` in prompt).

#### 3.2 File Watcher Mode (`--watch` / `-w`)
- **Behavior**: Continuous polling of `input/` at configurable intervals (`--interval`, default 3s).
- **Workflow**:
  - Detects new files in `input/` (non-hidden, recursive).
  - Atomically moves each file to `input/.processing/` before handling.
  - Moves completed files to `input/done/`; failed files to `input/failed/`.
  - Reuses a single persistent browser instance across all files.
  - Graceful shutdown via `request_watcher_shutdown()` on SIGINT/SIGTERM.

#### 3.3 Batch Folder Mode
- **Behavior**: One-shot execution of all pending files in the input directory.
- **Workflow**:
  - Discovers all non-hidden files under `input/`.
  - Sequentially processes prompts in a single browser context.
  - Produces a terminal completion summary (total, successes, failures).

#### 3.4 Single File Mode (`-i <file>`)
- **Behavior**: Direct processing of a specified Markdown prompt file.
- **Workflow**:
  - Validates input file existence.
  - Writes output to the specified target path.
  - Moves source file to `input/done/` on success, `input/failed/` on failure.

#### 3.5 Manual Login Mode (`--login`)
- **Behavior**: Opens a visible browser window on `chat.qwen.ai` and waits for the user to complete login or CAPTCHA resolution before saving the session.
- **Requirements**: Requires interactive TTY terminal.

#### 3.6 MCP Server Mode (`--mcp` / `src/mcp_server.py`)
- **Behavior**: Runs as a Model Context Protocol (MCP) server over stdio, exposing 1:1 capabilities of the CLI as tools for local AI agents.
- **Tools**: `qwen_send_prompt`, `qwen_process_single`, `qwen_process_batch`, `qwen_start_watcher`, `qwen_setup_session`, `qwen_get_audit_log`.

#### 3.7 Workspace Initialization Mode (`init` / `--init`)
- **Behavior**: Sets up local environment by creating `.agents/skills/qwen-web/SKILL.md` skill definition for agent discovery, `.qwen-web/` symlinks (`input`, `output`, `log`) pointing to XDG standard directories, and adding `.qwen-web/` to `.gitignore`.

---

### 4. Functional Requirements & Automation Pipeline

#### 4.1 Session & Security Management
- **Persistent Context**: Uses `launch_persistent_context` to retain cookies, LocalStorage, and login session in `qwen_session/`.
- **Anti-Automation Bypass**: Launches with `--disable-blink-features=AutomationControlled` and custom viewport.
- **Session Health Checks**: `SessionCheck.is_alive()` verifies page readiness and textarea presence; `SessionCheck.check_auth()` detects login redirects.
- **Security Check Interception**: Detects Cloudflare challenges and login redirects, raising `AuthRequiredError` with specific messages.

#### 4.2 Network & Performance Optimization
- **Resource Route Blocking**: Aborts requests for `png,jpg,jpeg,gif,webp,mp4,mp3,woff,woff2,ttf,otf` resources to reduce bandwidth and memory overhead.
- **Context Reuse**: Reuses existing pages or triggers navigation rather than hard browser reloads.
- **Stale Lock Cleanup**: `_clean_stale_locks()` removes orphaned Chrome lock files from previous sessions.

#### 4.3 Prompt Text Injection Engine
Supports ultra-large prompts (100k+ characters) via a **2-tier injection fallback** with error escalation:

1. **Tier 1 (React value setter + synthetic events)**: Native prototype setter on `HTMLTextAreaElement.prototype` with synthetic React `input` / `change` event dispatch. Most reliable for React-controlled `<textarea.message-input-textarea>`.
2. **Tier 2 (Clipboard Paste)**: Writes text to system clipboard and simulates `Ctrl/Cmd+V`. Covers contenteditable / edge cases where DOM property assignment is blocked.
3. **Tier 3 (fill() / type())**: Playwright native methods as last resort.

If all tiers fail, `PromptInjectionError` is raised.

#### 4.4 Response Generation & Stability Detection
- **Element Resiliency**: Fallback selector lists for chat inputs (`PRIMARY_TEXTAREA`, `FALLBACK_TEXTAREA`), submit buttons, and assistant message nodes.
- **Stability Loop**: Polls assistant message text at configurable intervals; marks generation complete when text is identical across N consecutive checks (default 3).
- **Output Validation**: `validate_response_content()` detects CAPTCHA challenges, server error pages, and empty responses before accepting output.

#### 4.5 Fault Handling & Automatic Recovery
- **Retry Mechanism**: Retries failed prompt operations up to 3 times with exponential backoff (2s, 4s, ... capped at 30s).
- **Page Re-initialization**: Navigates back to `chat.qwen.ai` between retry attempts.
- **Circuit Breaker**: Sliding-window failure tracking; trips after N consecutive failures within a time window, aborting further processing.
- **Rate Limiter**: Token-bucket throttling to prevent overwhelming the Qwen API.
- **Error Logging**: Appends detailed stack traces and timestamps to `log/errors.log` and JSONL audit trail.

---

### 5. Error Hierarchy

| Exception | Purpose |
| :--- | :--- |
| `QwenCliError` | Base exception for all CLI errors |
| `AuthRequiredError` | Session expired, CAPTCHA detected, or login redirect |
| `PromptInjectionError` | All injection strategies failed for prompt text |
| `ElementNotFoundError` | Required DOM element not found on page |
| `NetworkTimeoutError` | Browser network timeout or IPC error during streaming |
| `OutputValidationError` | Response content failed sanity check (empty, CAPTCHA, error page) |
| `BrowserLaunchError` | Playwright browser launch failed after retries |
| `CircuitBreakerOpenError` | Circuit breaker tripped; too many consecutive failures |
| `RateLimitError` | Rate limit exceeded |
| `FileUploadError` | File attachment upload failed |
| `FileValidationError` | Input file validation failed |
| `UploadTimeoutError` | File upload timed out |
| `UIInteractionError` | UI element interaction failed |
| `PipelineError` | Pipeline processing error |
| `QuarantineError` | File quarantine operation failed |
| `SendDispatchError` | Send button dispatch failed |
| `OutputWriteError` | Output file write failed |
| `SingleInstanceError` | Another instance is already running |

---

### 6. Observability Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| Structured Logging | `structlog` | JSON-formatted log events bound to run context |
| Distributed Tracing | OpenTelemetry (OTel SDK + OTLP HTTP exporter) | Span-level timing for each run and file |
| Error Monitoring | Sentry SDK | Exception capture with stack traces |
| Audit Trail | `log/audit_history.jsonl` | JSONL per-file record of status, durations, character counts |
| Output Metadata | HTML comment block in each output file | Run ID, source, timestamps, durations, character counts |
| Metadata Sidecar | `.meta.json` file alongside each output | Machine-readable JSON with same traceability data |

---

### 7. Traceability & Audit Trail

#### 7.1 Output File Metadata Header
Every generated output file begins with an HTML comment block:
- `Run ID` (timestamp + UUID hex)
- `Source File` & `Processed At` (ISO format)
- `Duration (seconds)`
- `Input Characters` vs. `Output Characters`

#### 7.2 Structured Audit Log (`log/audit_history.jsonl`)
- Format: JSON Lines (JSONL).
- Fields: `status` (`SUCCESS` / `FAILED`), `run_id`, file paths, character counts, execution duration, error messages.

---

### 8. Directory Layout

```text
qwen-web/
├── input/
│   ├── (root)          # Drop .md files here (todo source)
│   ├── done/           # Completed input files
│   ├── failed/         # Files that failed after all retries
│   └── .processing/    # Temporary atomic lock directory
├── output/             # Generated AI response .md files + .meta.json sidecars
├── log/                # Structured logs & audit_history.jsonl
└── qwen_session/       # Persistent Playwright browser profile
```

---

### 9. Non-Functional Requirements

- **Performance**: Polling overhead under 300ms per cycle; route blocking reduces network usage by ~40–60%.
- **Reliability**: Atomic file moves via `safe_move`; no input file loss during processing failures.
- **Usability**: ANSI terminal color output, clean summary panels, live progress indicators.
- **Observability**: All significant events emit structured log entries and OTel spans for traceability.
- **Type Safety**: Modern Python typing (`dict[str, Any]`, `Path | None`, `str | None`); validated constructor parameters for `CircuitBreaker` and `RateLimiter`.
- **Error Specificity**: Playwright exceptions caught by type (`PlaywrightError`, `PlaywrightTimeoutError`) rather than generic `Exception`.

---

### 10. Recent Changes (v1.1.0)

- **Module decomposition**: Split `qwen_client.py` into focused modules (`prompt_injector.py`, `sender.py`, `streamer.py`, `saver.py`, `file_uploader.py`).
- **Centralized error hierarchy**: Added `NetworkTimeoutError`, `OutputValidationError`, and 10+ domain-specific exceptions in `types.py`.
- **Output validation**: `validate_response_content()` detects CAPTCHA challenges and server error pages before accepting AI response.
- **Type annotations**: Updated to modern Python syntax; fixed `XDG_CACHE_HOME` env var bug.
- **Performance**: `CircuitBreaker` and `RateLimiter` now use `deque` for O(1) operations instead of `list.pop(0)`.
- **Exception handling**: Replaced generic `except Exception` with specific `PlaywrightError`, `PlaywrightTimeoutError`, `OSError` catches.
- **Graceful shutdown**: Dual shutdown flag system (`_shutdown_flag` + `request_watcher_shutdown()`) for coordinated watcher termination.
