# Product Requirements Document (PRD)
## Qwen AI Web Automation CLI (`qwen-web-automation`)

---

### 1. Overview & Vision

`qwen-web-automation` is a production-grade, resilient CLI automation tool that interacts with the Qwen AI web interface (`chat.qwen.ai`) without requiring official API keys. It enables batch prompt processing, real-time file watching, persistent session management, structured observability (structlog + OpenTelemetry + Sentry), and JSONL audit logging via Playwright browser automation.

---

### 2. Architecture & Module Layout

| Module | Responsibility |
| :--- | :--- |
| `src/main.py` | CLI entrypoint, argument parser, interactive TUI menu |
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
Supports ultra-large prompts (100k+ characters) via a **3-tier injection fallback**:

1. **Tier 1 (Direct DOM JS Injection)**: Native prototype setter on `HTMLTextAreaElement.prototype` with synthetic React `input` / `change` event dispatch.
2. **Tier 2 (Playwright `fill()`)**: Standard automated field filling.
3. **Tier 3 (Clipboard Paste)**: Writes text to system clipboard and simulates `Ctrl+V`.

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
qwen-web-automation/
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

| Flag / Option  | Short | Default Value          | Description |
| :--- | :--- | :--- | :--- |
| `--input`      | `-i`  | `BASE_DIR/input`           | Input Markdown file or directory |
| `--output`     | `-o`  | `BASE_DIR/output`          | Output file or directory |
| `--done-dir`   | `-d`  | `BASE_DIR/input/done`      | Target folder for completed input files |
| `--failed-dir` | N/A   | `BASE_DIR/input/failed`    | Target folder for failed input files |
| `--proc-dir`   | N/A   | `BASE_DIR/input/.processing` | Temporary processing directory |
| `--log-dir`    | N/A   | `BASE_DIR/log`             | Directory for logs and audit trail |
| `--watch`      | `-w`  | `False`                    | Enable continuous folder watcher mode |
| `--interval`   | N/A   | `3`                        | Polling interval (seconds) for watcher mode |
| `--headless`   | N/A   | `False`                    | Run browser in headless background mode |
| `--data-dir`   | N/A   | `BASE_DIR/qwen_session`    | Browser session data directory |
| `--timeout`    | N/A   | `300`                      | Maximum response wait time (seconds) |
| `--login`      | N/A   | `False`                    | Open browser for manual login & session save |

---

### 9. Non-Functional Requirements

- **Performance**: Polling overhead under 300ms per cycle; route blocking reduces network usage by ~40–60%.
- **Reliability**: Atomic file moves via `safe_move`; no input file loss during processing failures.
- **Usability**: ANSI terminal color output, clean summary panels, live progress indicators.
- **Observability**: All significant events emit structured log entries and OTel spans for traceability.
