# PRD — Qwen AI Web Automation CLI (`qwen-web`)

## 1. Concept

A resilient CLI + MCP server that drives `chat.qwen.ai` via Playwright — no API key needed. Supports batch processing, file watching, persistent sessions, and 1:1 MCP tooling for local AI agents. Built-in observability (structlog + OpenTelemetry + Sentry) and JSONL audit logging.

## 2. Operating Modes

- **Interactive (no args)**: Menu — Watcher, Batch, Single, Login, Init, Exit. Headed/headless choice; `Ctrl+C` safe.
- **Watcher (`--watch`)**: Polls `input/` (default 3s), atomically moves files to `.processing/`, runs on one browser, sorts to `done/`/`failed/`. SIGINT/SIGTERM shutdown.
- **Batch**: One-shot run of all `input/` files in a single context; prints summary (total/success/fail).
- **Single (`-i <file>`)**: One file → output path; source moved to `done/` or `failed/`.
- **Login (`--login`)**: Visible browser, waits for auth/CAPTCHA; saves session. Needs TTY.
- **MCP (`--mcp`)**: stdio MCP server exposing CLI as tools — `qwen_send_prompt`, `qwen_process_single`, `qwen_process_batch`, `qwen_start_watcher`, `qwen_setup_session`, `qwen_get_audit_log`.
- **Init**: Creates agent skill, `.qwen-web/` XDG symlinks (`input`/`output`/`log`), adds to `.gitignore`.

## 3. Pipeline

- **Session**: `launch_persistent_context` (cookies, LocalStorage) in `qwen_session/`. Anti-automation flag + custom viewport. `is_alive()` / `check_auth()` health checks. Detects Cloudflare/login redirect → `AuthRequiredError`.
- **Perf**: Block image/font/media routes (~40–60% less traffic). Reuse pages, not reloads. Cleanup stale Chrome locks.
- **Injection (3 tiers, escalate on failure)**:
  1. React value setter + synthetic events.
  2. Clipboard paste (`Ctrl/Cmd+V`).
  3. Playwright `fill()`/`type()`.
  All fail → `PromptInjectionError`.
- **Stability**: Fallback selectors for input/submit/assistant nodes. Poll output; complete when text stable across 3 checks. `validate_response_content()` rejects CAPTCHA/error/empty.
- **Recovery**: Retry ≤3× with backoff (2s→30s cap), re-navigate between tries. Circuit breaker (sliding window) + token-bucket rate limiter. Logs to `log/errors.log` + JSONL audit.

## 4. Error Hierarchy

`QwenCliError` (base) → `AuthRequiredError`, `PromptInjectionError`, `ElementNotFoundError`, `NetworkTimeoutError`, `OutputValidationError`, `BrowserLaunchError`, `CircuitBreakerOpenError`, `RateLimitError`, `FileUploadError`, `FileValidationError`, `UploadTimeoutError`, `UIInteractionError`, `PipelineError`, `QuarantineError`, `SendDispatchError`, `OutputWriteError`, `SingleInstanceError`.

## 5. Observability

- **Logging**: `structlog` (JSON, run-bound).
- **Tracing**: OpenTelemetry (OTLP HTTP).
- **Errors**: Sentry capture.
- **Audit**: `log/audit_history.jsonl` (per-file status, durations, char counts).
- **Metadata**: HTML comment header + `.meta.json` sidecar per output.

## 6. Directory Layout

```text
qwen-web/
├── input/
│   ├── (root)         # Drop .md files
│   ├── done/          # Completed
│   ├── failed/        # Failed after retries
│   └── .processing/   # Atomic lock
├── output/            # Responses + .meta.json
├── log/               # Logs + audit_history.jsonl
└── qwen_session/      # Persistent profile
```

## 7. Non-Functional

- **Performance**: Poll overhead <300ms/cycle.
- **Reliability**: Atomic `safe_move`; no input loss.
- **Usability**: ANSI colors, summary panels, live progress.
- **Type Safety**: Modern typing; typed constructors.
- **Errors**: Catch Playwright errors by type, not `Exception`.
