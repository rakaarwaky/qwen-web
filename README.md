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
- **2-Tier Prompt Injection**: Handles large prompts (100k+ chars) via React prototype setter + synthetic events, with clipboard paste fallback.
- **Structured Observability**: Structured JSON logging via `structlog`, OpenTelemetry tracing, Sentry error reporting, and JSONL audit trail.
- **Fault Recovery**: Automatic retry up to 3 times with page re-initialization on failure.

---

## Repository Structure

```text
qwen-web-automation/
├── src/
│   ├── main.py             # CLI entrypoint & argument parser
│   ├── mcp_server.py       # MCP Server exposing 1:1 CLI features as MCP tools
│   ├── config.py           # Constants, dataclasses, custom exceptions
│   ├── browser.py          # Playwright browser session management
│   ├── qwen_client.py      # Core automation: injection, response detection
│   ├── pipeline.py         # File pipeline: watcher, batch, single file
│   └── observability.py    # structlog, OTel, Sentry setup
├── tests/
│   ├── unit_qwen_auto.py
│   ├── integration_qwen_auto.py
│   ├── e2e_qwen_auto.py
│   ├── regression_qwen_auto.py
│   ├── smoke_qwen_auto.py
│   └── contract_qwen_auto.py
├── input/                  # Drop new .md prompt files here (root of todo)
│   ├── done/               # Processed files moved here
│   ├── failed/             # Files that failed after all retries
│   └── .processing/        # Temporary lock directory during processing
├── output/                 # Generated AI response .md files
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
git clone https://github.com/rakaarwaky/qwen-web-automation.git
cd qwen-web-automation
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
│ 5. Exit                                          │
╰──────────────────────────────────────────────────╯
Select [1-5, default=1]:
Run headless? [y/N, default=N]:
```

---

## Usage Modes

### 1. Real-Time File Watcher Mode (`--watch`)

Monitors `input/` every N seconds. Drop any `.md` file into `input/` while the watcher is running to process it automatically.

```bash
python3 src/main.py --watch --headless
```

### 2. Batch Folder Mode

Processes all current files inside `input/` once and exits upon completion:

```bash
python3 src/main.py -i input -o output --headless
```

### 3. Single File Mode

Processes a specific Markdown file directly:

```bash
python3 src/main.py -i my_prompt.md -o output/result.md --headless
```

### 4. Manual Login / Session Setup

```bash
python3 src/main.py --login
```

> **Note on Initial Setup:** On your very first run, execute without `--headless` (or use `--login`) so you can manually log into your Qwen AI account in the browser window. All future runs can use `--headless`.

---

## CLI Reference

| Flag / Option     | Argument | Description                                              | Default           |
| :---------------- | :------- | :------------------------------------------------------- | :---------------- |
| `-w, --watch`     | None     | Enable continuous File Watcher mode                      | disabled          |
| `--interval`      | `INT`    | Polling interval in seconds for watcher mode             | `3`               |
| `-i, --input`     | `PATH`   | Input markdown file or directory                         | `input/`          |
| `-o, --output`    | `PATH`   | Output markdown file or directory                        | `output/`         |
| `-d, --done-dir`  | `PATH`   | Directory to move completed input files                  | `input/done`      |
| `--failed-dir`    | `PATH`   | Directory to move failed input files                     | `input/failed`    |
| `--proc-dir`      | `PATH`   | Temporary directory used during processing               | `input/.processing` |
| `--log-dir`       | `PATH`   | Directory for structured logs and audit trail            | `log/`            |
| `--headless`      | None     | Run browser in background without GUI window             | false             |
| `--data-dir`      | `PATH`   | Directory storing browser profile & cookies              | `./qwen_session`  |
| `--timeout`       | `INT`    | Max wait time in seconds for AI response                 | `300`             |
| `--login`         | None     | Open browser to log in manually and save session         | disabled          |

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
