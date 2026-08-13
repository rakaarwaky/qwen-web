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

---

## Key Features

- **MCP Server Integration (1:1 with CLI)**: Connect local AI agents directly via MCP tools.
- **Real-Time File Watcher Mode**: Monitors `input/` for new `.md` files, processes them automatically.
- **Batch Folder Pipeline**: Processes entire directories of Markdown files sequentially.
- **Interactive Terminal UI**: Run with no arguments to open an interactive selection menu.
- **Persistent Session Login**: Log in once, then run in `--headless` mode indefinitely.
- **Smart Response Detection**: Polls AI generation progress dynamically until completion.
- **Output Validation**: Detects CAPTCHA challenges and server error pages before accepting output.
- **2-Tier Prompt Injection**: Handles large prompts (100k+ chars) via React setter + clipboard fallback.
- **Structured Observability**: `structlog`, OpenTelemetry, Sentry, JSONL audit trail.
- **Fault Recovery**: Automatic retry with circuit breaker and rate limiting.

---

## Installation

```bash
git clone https://github.com/rakaarwaky/qwen-web.git
cd qwen-web
pip install -r requirements.txt
python3 -m playwright install chromium
```

---

## Quick Start

```bash
qwen-web-cli
```

### Interactive Menu

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

### Workspace Initialization

```bash
qwen-web-cli init
```

### File Watcher Mode

```bash
qwen-web-cli --watch --headless
```

### Batch Folder Mode

```bash
qwen-web-cli -i input -o output --headless
```

### Single File Mode

```bash
qwen-web-cli -i my_prompt.md -o output/result.md --headless
```

### Manual Login

```bash
qwen-web-cli --login
```

> First run requires `--login` or interactive mode for manual authentication. Subsequent runs can use `--headless`.

### MCP Server Mode

```bash
qwen-web-mcp
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
| `--proc-dir`           | `PATH`   | Temporary lock directory during processing               | `~/.cache/qwen-web/.processing` |
| `--log-dir`            | `PATH`   | Directory for structured logs and audit trail            | `~/.local/state/qwen-web/log` |
| `--data-dir`           | `PATH`   | Browser profile & session cookies directory              | `~/.local/share/qwen-web/qwen_session` |
| `--headless`           | None     | Run browser in background without GUI window             | false                       |
| `--login`              | None     | Open browser to log in manually and save session         | disabled                    |
| `--mcp`                | None     | Run as MCP server over stdio                             | disabled                    |
| `--timeout`            | `INT`    | Max wait time in seconds for AI response                 | `300`                       |
| `--request-timeout`    | `INT`    | Max seconds to wait for network response                 | `120`                       |
| `--poll-interval`      | `FLOAT`  | Seconds between message-poll DOM checks                  | `1.0`                       |
| `--streaming-timeout`  | `INT`    | Max streaming duration in seconds                        | `180`                       |
| `--rate-limit`         | `INT`    | Max prompt requests per minute                           | `60`                        |
| `--cb-threshold`       | `INT`    | Consecutive failures before tripping circuit breaker     | `5`                         |
| `--cb-window`          | `INT`    | Circuit breaker sliding window in seconds                | `30`                        |
| `--retry-failed`       | None     | Re-process files in `failed/` directory on next run      | disabled                    |

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
