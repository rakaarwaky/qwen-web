<div align="center">

# Qwen AI Web Automation CLI & MCP Server

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
- **Multi-Tier Prompt Injection**: Handles large prompts (100k+ chars) via React setter, ContentEditable, and Playwright fallbacks.
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

The login command first validates the saved session. If it is already valid, the
CLI reports that state and does not open a visible browser. Otherwise, it opens
a headed browser and keeps it open while you complete login or CAPTCHA; press `ENTER`
only after the chat page is ready. The CLI verifies the resulting session before
reporting success. Subsequent runs can use `--headless`.

### MCP Server Mode

```bash
qwen-web-mcp
```

---

## CLI Reference

Only the flags below are needed for daily use. All tuning values (timeouts, poll interval, rate limit, circuit-breaker thresholds, and directory paths) are **hardcoded to safe defaults** in `modules/root_cli_main_entry.py` and follow the XDG Base Directory spec — you normally never pass them.

| Command / Flag   | Argument | Description                                            |
| :--------------- | :------- | :----------------------------------------------------- |
| `qwen-web-cli init` | `[DIR]` | Provision workspace (`.agents/skills`, `.qwen-web`). Run once. |
| `qwen-web-cli --login` | None | Open a visible browser to log in and save the session. Run once. |
| `-i, --input`   | `PATH`   | Input markdown file or directory (required each run).  |
| `-o, --output`  | `PATH`   | Output markdown file or directory (required each run). |
| `-w, --watch`   | None     | Enable continuous File Watcher mode.                   |
| `--headless`    | None     | Run the browser in the background without a GUI window.|
| `qwen-web-mcp`  | None     | Run as a Model Context Protocol (MCP) server over stdio. |

> All other options (polling interval, done/failed/proc/log/data directories, timeout, request-timeout, streaming-timeout, poll-interval, rate-limit, circuit-breaker threshold/window, `--retry-failed`) are pre-configured defaults and omitted from the CLI surface for simplicity.

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
