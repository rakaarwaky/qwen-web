<div align="center">

# Qwen AI Web Automation CLI

**Automate Markdown-based prompt processing via Qwen AI Web (`chat.qwen.ai`)**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-1.62%2B-green.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Headless Mode](https://img.shields.io/badge/browser-headless%20supported-purple.svg)]()

[Features](#key-features) • [Installation](#installation) • [Quick Start](#quick-start) • [Usage Modes](#usage-modes) • [CLI Reference](#cli-reference)

</div>

---

## Overview

**Qwen AI Web Automation CLI & MCP Server** is a lightweight, production-grade automation pipeline and Model Context Protocol (MCP) server that sends Markdown prompt files (`.md`) or direct strings to **Qwen AI (`chat.qwen.ai`)**, waits for the AI to complete its response, extracts the output, and saves it locally — no API key required.

It supports **MCP Server integration for local AI agents**, **real-time file watching**, **folder batch processing**, **single file mode**, and an **interactive CLI menu**.

---

## Key Features

- **MCP Server Integration (1:1 with CLI)**: Connect local AI agents (Claude Desktop, Continue, Gemini CLI, etc.) directly via MCP tools (`qwen_send_prompt`, `qwen_process_single`, `qwen_process_batch`, `qwen_start_watcher`, `qwen_setup_session`, `qwen_get_audit_log`).
- **Real-Time File Watcher Mode**: Monitors `input/` for new `.md` files, processes them automatically, saves outputs to `output/`, and moves completed inputs to `input/done/`.
- **Batch Folder Pipeline**: Processes entire directories of Markdown files sequentially in a single persistent browser session.
- **Interactive Terminal UI**: Run `python3 src/main.py` with no arguments to open an interactive selection menu.
- **Persistent Session Login**: Retains session cookies in `./qwen_session`. Log in once, then run in `--headless` mode indefinitely.
- **Smart Response Detection**: Polls AI generation progress dynamically; handles streaming until completion before writing output.
- **Output Validation**: Detects CAPTCHA challenges, server error pages, and empty responses before accepting AI output.
- **2-Tier Prompt Injection**: Handles large prompts (100k+ chars) via React prototype setter + synthetic events, with clipboard paste fallback.
- **Structured Observability**: Structured JSON logging via `structlog`, OpenTelemetry tracing, Sentry error reporting, and JSONL audit trail.
- **Fault Recovery**: Automatic retry up to 3 times with page re-initialization on failure; circuit breaker and rate limiting for resilience.
- **Type-Safe**: Modern Python typing with validated constructors and specific exception hierarchy.

---

## Repository Structure

```text
qwen-web/
├── src/
│   ├── main.py             # CLI entrypoint & argument parser
│   ├── mcp_server.py       # MCP Server exposing 1:1 CLI features as MCP tools
│   ├── types.py            # Type definitions, AppConfig, exceptions, CircuitBreaker, RateLimiter
│   ├── browser.py          # Playwright browser session management & health checks
│   ├── qwen_client.py      # Core automation orchestrator
│   ├── prompt_injector.py  # DOM text injection (React setter + clipboard fallback)
│   ├── sender.py           # Send button click, message counting, latest message
│   ├── streamer.py         # Response streaming detection & output validation
│   ├── saver.py            # Output file writing with metadata traceability
│   ├── file_uploader.py    # File attachment upload via Playwright file chooser
│   ├── pipeline.py         # File pipeline: watcher, batch, single file, retry logic
│   └── observability.py    # structlog, OTel, Sentry setup
├── tests/
│   ├── unit_qwen_auto.py
│   ├── integration_qwen_auto.py
│   ├── e2e_qwen_auto.py
│   ├── regression_qwen_auto.py
│   ├── smoke_qwen_auto.py
│   ├── contract_qwen_auto.py
│   ├── test_qwen_client_behavior.py
│   ├── test_pipeline_fixtures.py
│   ├── test_e2e_pipeline.py
│   └── manual_probe.py
├── input/                  # Drop new .md prompt files here (root of todo)
│   ├── done/               # Processed files moved here
│   ├── failed/             # Files that failed after all retries
│   └── .processing/        # Temporary lock directory during processing
├── output/                 # Generated AI response .md files + .meta.json sidecars
├── log/                    # Structured logs and audit_history.jsonl
├── qwen_session/           # Persistent browser profile & session cookies
├── requirements.txt        # Python dependencies
├── PRD.md                  # Product Requirements Document
└── README.md               # Project documentation
```

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/rakaarwaky/qwen-web.git
cd qwen-web
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
python3 -m playwright install chromium
```

---

## Quick Start

Run without flags to launch the **Interactive Menu**:

```bash
python3 src/main.py
```

### Interactive Menu Interface

```text
╭─ qwen-cli interactive setup ─────────────────────╮
│ 1. Watcher Mode (continuous)                     │
│ 2. Batch Mode (folder)                           │
│ 3. Single File Mode                              │
│ 4. Manual Login / Session Setup                  │
│ 5. Init Workspace                                │
│ 6. Exit                                          │
╰──────────────────────────────────────────────────╯
Select [1-6, default=1]:
Run headless? [y/N, default=N]:
```

---

## Usage Modes

### 1. Workspace Initialization (`init` / `--init`)

Initializes local environment with `.agents/skills/qwen-web/SKILL.md` skill definition, creates `.qwen-web/` symlinks (`input`, `output`, `log`) to XDG standard paths (`~/.local/share/qwen-web`, `~/.local/state/qwen-web`), and updates `.gitignore`:

```bash
python3 src/main.py init
# or
python3 src/main.py --init
```

### 2. Real-Time File Watcher Mode (`--watch`)

Monitors input directory every N seconds. Drop any `.md` file into input directory while the watcher is running to process it automatically.

```bash
python3 src/main.py --watch --headless
```

### 3. Batch Folder Mode

Processes all current files inside `input/` once and exits upon completion:

```bash
python3 src/main.py -i input -o output --headless
```

### 4. Single File Mode

Processes a specific Markdown file directly:

```bash
python3 src/main.py -i my_prompt.md -o output/result.md --headless
```

### 5. Manual Login / Session Setup

```bash
python3 src/main.py --login
```

> **Note on Initial Setup:** On your very first run, execute without `--headless` (or use `--login`) so you can manually log into your Qwen AI account in the browser window. All future runs can use `--headless`.

### 6. MCP Server Mode (`--mcp`)

Runs as a Model Context Protocol (MCP) server over stdio for local AI agents:

```bash
python3 src/main.py --mcp
```

---

## CLI Reference

| Flag / Option          | Argument | Description                                              | Default                     |
| :--------------------- | :------- | :------------------------------------------------------- | :-------------------------- |
| `init`, `--init`       | `[DIR]`  | Initialize workspace with `.agents/skills` & `.qwen-web` | Current directory (`.`)     |
| `-w, --watch`          | None     | Enable continuous File Watcher mode                      | disabled                    |
| `--interval`           | `INT`    | Polling interval in seconds for watcher mode             | `3`                         |
| `-i, --input`          | `PATH`   | Input markdown file or directory                         | `~/.local/share/qwen-web/input` |
| `-o, --output`         | `PATH`   | Output markdown file or directory                        | `~/.local/share/qwen-web/output` |
| `-d, --done-dir`       | `PATH`   | Directory to move completed input files                  | `~/.local/share/qwen-web/input/done` |
| `--failed-dir`         | `PATH`   | Directory to move failed input files                     | `~/.local/share/qwen-web/input/failed` |
| `--proc-dir`           | `PATH`   | Temporary lock directory used during processing           | `~/.cache/qwen-web/.processing` |
| `--log-dir`            | `PATH`   | Directory for structured logs and audit trail            | `~/.local/state/qwen-web/log` |
| `--data-dir`           | `PATH`   | Directory storing browser profile & session cookies      | `~/.local/share/qwen-web/qwen_session` |
| `--headless`           | None     | Run browser in background without GUI window             | false                       |
| `--login`              | None     | Open browser to log in manually and save session         | disabled                    |
| `--mcp`                | None     | Run as Model Context Protocol (MCP) server over stdio    | disabled                    |
| `--timeout`            | `INT`    | Max wait time in seconds for AI response                 | `300`                       |
| `--request-timeout`    | `INT`    | Max seconds to wait for Qwen network response            | `120`                       |
| `--poll-interval`      | `FLOAT`  | Seconds between message-poll DOM checks                  | `1.0`                       |
| `--streaming-timeout`  | `INT`    | Max duration in seconds for streaming response           | `180`                       |
| `--rate-limit`         | `INT`    | Max prompt requests per minute                           | `60`                        |
| `--cb-threshold`       | `INT`    | Consecutive failures before tripping circuit breaker     | `5`                         |
| `--cb-window`          | `INT`    | Circuit breaker sliding window in seconds                | `30`                        |
| `--retry-failed`       | None     | Re-process files in `failed/` directory on next run      | disabled                    |

---

## Error Handling

The application uses a structured exception hierarchy:

| Exception | When Raised |
| :--- | :--- |
| `AuthRequiredError` | Session expired, CAPTCHA detected, or login redirect |
| `PromptInjectionError` | All injection strategies failed for prompt text |
| `NetworkTimeoutError` | Browser network timeout or IPC error during streaming |
| `OutputValidationError` | Response content failed sanity check (empty, CAPTCHA, error page) |
| `CircuitBreakerOpenError` | Too many consecutive failures; processing aborted |
| `BrowserLaunchError` | Playwright browser launch failed after retries |

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
