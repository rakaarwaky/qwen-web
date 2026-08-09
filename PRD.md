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
| `src/config.py` | Constants, path defaults, DOM selectors, `AppConfig` dataclass, custom exceptions |
| `src/browser.py` | Playwright `launch_persistent_context` lifecycle management |
| `src/qwen_client.py` | Core automation: prompt injection, response polling, security check interception |
| `src/pipeline.py` | File pipeline: watcher loop, batch processor, single file handler, retry logic, `AuditLog` |
| `src/observability.py` | `structlog` setup, OpenTelemetry tracing, Sentry SDK initialization, span helpers |

---

### 3. Core Operating Modes

#### 3.1 Interactive Terminal UI (TUI) Mode
- **Trigger**: Script executed without CLI arguments.
- **Features**:
  - Selection menu: Watcher, Batch, Single File, Manual Login, Exit.
  - Prompts for headless vs. headed browser mode.
  - Graceful keyboard interrupt handling (`Ctrl+C`).

#### 3.2 File Watcher Mode (`--watch` / `-w`)
- **Behavior**: Continuous polling of `input/` at configurable intervals (`--interval`, default 3s).
- **Workflow**:
  - Detects new files in `input/` (non-hidden, recursive).
  - Atomically moves each file to `input/.processing/` before handling.
  - Moves completed files to `input/done/`; failed files to `input/failed/`.
  - Reuses a single persistent browser instance across all files.

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

#### 3.6 MCP Server Mode (`--mcp` / `src/mcp_server.py`)
- **Behavior**: Runs as a Model Context Protocol (MCP) server over stdio, exposing 1:1 capabilities of the CLI as tools (`qwen_send_prompt`, `qwen_process_single`, `qwen_process_batch`, `qwen_start_watcher`, `qwen_setup_session`, `qwen_get_audit_log`) for local AI agents.

#### 3.7 Workspace Initialization Mode (`init` / `--init`)
- **Behavior**: Sets up local environment by creating `.agents/skills/qwen-web/SKILL.md` skill definition for agent discovery, `.qwen-web/` symlinks (`input`, `output`, `log`) pointing to XDG standard directories, and adding `.qwen-web/` to `.gitignore`.

---

### 4. Functional Requirements & Automation Pipeline

#### 4.1 Session & Security Management
- **Persistent Context**: Uses `launch_persistent_context` to retain cookies, LocalStorage, and login session in `qwen_session/`.
- **Anti-Automation Bypass**: Launches with `--disable-blink-features=AutomationControlled` and custom viewport.
- **Security Check Interception**: Detects Cloudflare challenges and login redirects (`/login`, `/signin`), pausing execution and prompting the user in headed mode.

#### 4.2 Network & Performance Optimization
- **Resource Route Blocking**: Aborts requests for `image`, `media`, and `font` resources to reduce bandwidth and memory overhead (~40–60% reduction).
- **Context Reuse**: Reuses existing pages or triggers "New Chat" rather than performing hard browser reloads.

#### 4.3 Prompt Text Injection Engine
Supports ultra-large prompts (100k+ characters) via a **2-tier injection fallback**:

1. **Tier 1 (React value setter + synthetic events)**: Native prototype setter on `HTMLTextAreaElement.prototype` with synthetic React `input` / `change` event dispatch. Most reliable for React-controlled `<textarea.message-input-textarea>`.
2. **Tier 2 (Clipboard Paste)**: Writes text to system clipboard and simulates `Ctrl/Cmd+V`. Covers contenteditable / edge cases where DOM property assignment is blocked.

Playwright `fill()` and raw `type()` were removed: `fill()` does not trigger React state updates, and `type()` is O(n) slow for 100k+ char prompts. If both tiers fail, `PromptInjectionError` is raised.

#### 4.4 Response Generation & Stability Detection
- **Element Resiliency**: Fallback selector lists for chat inputs, submit buttons, and assistant message nodes.
- **Fast Adaptive Wait**: Polls for initial DOM node creation (up to 5s) before entering the stability loop.
- **Stability Loop**: Polls assistant message text every 300ms; marks generation complete when text is identical across 5 consecutive checks (1.5s stability window). Displays live terminal spinner with character count.

#### 4.5 Fault Handling & Automatic Recovery
- **Retry Mechanism**: Retries failed prompt operations up to 3 times (`process_file_with_retry`).
- **Page Re-initialization**: Navigates to `about:blank` between retry attempts.
- **Error Logging**: Appends detailed stack traces and timestamps to `log/errors.log`.

---

### 5. Observability Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| Structured Logging | `structlog` | JSON-formatted log events bound to run context |
| Distributed Tracing | OpenTelemetry (OTel SDK + OTLP HTTP exporter) | Span-level timing for each run and file |
| Error Monitoring | Sentry SDK | Exception capture with stack traces |
| Audit Trail | `log/audit_history.jsonl` | JSONL per-file record of status, durations, character counts |
| Output Metadata | HTML comment block in each output file | Run ID, source, timestamps, durations, character counts |

---

### 6. Traceability & Audit Trail

#### 6.1 Output File Metadata Header
Every generated output file begins with an HTML comment block:
- `Run ID` (timestamp + UUID hex)
- `Source File` & `Processed At`
- `Duration (seconds)`
- `Input Characters` vs. `Output Characters`

#### 6.2 Structured Audit Log (`log/audit_history.jsonl`)
- Format: JSON Lines (JSONL).
- Fields: `status` (`SUCCESS` / `FAILED`), `run_id`, file paths, character counts, execution duration, error messages.

---

### 7. Directory Layout

```text
qwen-web/
├── input/
│   ├── (root)          # Drop .md files here (todo source)
│   ├── done/           # Completed input files
│   ├── failed/         # Files that failed after all retries
│   └── .processing/    # Temporary atomic lock directory
├── output/             # Generated AI response .md files
├── log/                # Structured logs & audit_history.jsonl
└── qwen_session/       # Persistent Playwright browser profile
```

---

### 8. CLI Arguments & Configuration Matrix

| Flag / Option | Short | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `init`, `--init` | N/A | `.` | Initialize workspace (`.agents/skills` & `.qwen-web` symlinks) |
| `--input` | `-i` | `~/.local/share/qwen-web/input` | Input Markdown file or directory |
| `--output` | `-o` | `~/.local/share/qwen-web/output` | Output file or directory |
| `--done-dir` | `-d` | `~/.local/share/qwen-web/input/done` | Target folder for completed input files |
| `--failed-dir` | N/A | `~/.local/share/qwen-web/input/failed` | Target folder for failed input files |
| `--proc-dir` | N/A | `~/.cache/qwen-web/.processing` | Temporary atomic processing lock directory |
| `--log-dir` | N/A | `~/.local/state/qwen-web/log` | Directory for structured logs and audit trail |
| `--data-dir` | N/A | `~/.local/share/qwen-web/qwen_session` | Browser profile & persistent session storage |
| `--watch` | `-w` | `False` | Enable continuous folder watcher mode |
| `--interval` | N/A | `3` | Polling interval (seconds) for watcher mode |
| `--headless` | N/A | `False` | Run browser in headless background mode |
| `--login` | N/A | `False` | Open browser for manual login & session save |
| `--mcp` | N/A | `False` | Run as Model Context Protocol (MCP) server over stdio |
| `--timeout` | N/A | `300` | Maximum response wait time (seconds) |
| `--request-timeout` | N/A | `120` | Max seconds to wait for network response |
| `--poll-interval` | N/A | `1.0` | Seconds between DOM polling checks |
| `--streaming-timeout` | N/A | `180` | Max streaming duration in seconds |
| `--rate-limit` | N/A | `60` | Max prompt requests per minute |
| `--cb-threshold` | N/A | `5` | Consecutive failures before tripping circuit breaker |
| `--cb-window` | N/A | `30` | Circuit breaker sliding window in seconds |
| `--retry-failed` | N/A | `False` | Process files in `failed/` directory on next run |

---

### 9. Non-Functional Requirements

- **Performance**: Polling overhead under 300ms per cycle; route blocking reduces network usage by ~40–60%.
- **Reliability**: Atomic file moves via `safe_move`; no input file loss during processing failures.
- **Usability**: ANSI terminal color output, clean summary panels, live progress indicators.
- **Observability**: All significant events emit structured log entries and OTel spans for traceability.
