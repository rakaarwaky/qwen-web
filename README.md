<div align="center">

# Qwen AI Web Automation CLI & MCP Server

</div>

---

## Overview

**Qwen AI Web Automation CLI & MCP Server** is a lightweight, production-grade automation pipeline and Model Context Protocol (MCP) server that sends Markdown prompt files (`.md`) or direct strings to **Qwen AI (`chat.qwen.ai`)**, waits for the AI to complete its response, extracts the output, and saves it locally — no API key required.

---

## Key Features

- **MCP Server Integration (1:1 with CLI)**: Connect local AI agents directly via MCP tools.
- **Subcommand CLI Pipeline**: Dedicated subcommands for direct prompts, prompt files, and document attachments.
- **Interactive Terminal UI**: Run `qwen-web-cli` with no arguments to open an interactive selection menu.
- **Persistent Session Login**: Log in once via `qwen-web-cli login`, then run headlessly.
- **Smart Response Detection**: Polls AI generation progress dynamically until completion.
- **Output Validation**: Detects CAPTCHA challenges and server error pages before accepting output.
- **Multi-Tier Prompt Injection**: Handles large prompts via React setter, ContentEditable, and Playwright fallbacks.
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
│ 1. Direct Prompt                                 │
│ 2. Single Prompt File                            │
│ 3. Prompt File with Attachment                   │
│ 4. Session Setup (Login)                         │
│ 5. Init Workspace                                │
│ 6. Exit                                          │
╰──────────────────────────────────────────────────╯
```

---

## Usage Subcommands

### Workspace Initialization

```bash
qwen-web-cli init
```

### Direct Inline Prompt

```bash
qwen-web-cli prompt-direct -t "Summarize quantum computing" -o output/result.md --headless
```

### Single Prompt File Processing

```bash
qwen-web-cli prompt-only -i prompt.md -o output/result.md --headless
```

### Prompt File Processing with Attachment

```bash
qwen-web-cli prompt-with-attachment -i prompt.md -a document.pdf -o output/result.md --headless
```

### Manual Login / Session Setup

```bash
qwen-web-cli login
```

The `login` subcommand opens a visible browser and keeps it open while you complete login or CAPTCHA. Subsequent runs can use `--headless`.

### MCP Server Mode

```bash
qwen-web-mcp
```

---

## CLI Reference

| Subcommand | Argument | Description |
| :--- | :--- | :--- |
| `qwen-web-cli init` | `[--dir DIR]` | Provision workspace (`.agents/skills`, `.qwen-web`). Run once. |
| `qwen-web-cli login` | `[--headless]` | Open a browser to log in and save session. Run once. |
| `qwen-web-cli prompt-direct` | `-t TEXT [-o OUT] [--headless]` | Send inline text prompt directly to Qwen. |
| `qwen-web-cli prompt-only` | `-i PROMPT [-o OUT] [--headless]` | Process a Markdown prompt file. |
| `qwen-web-cli prompt-with-attachment` | `-i PROMPT -a ATTACH [-o OUT] [--headless]` | Process a prompt file with document attachment. |
| `qwen-web-mcp` | None | Run as a Model Context Protocol (MCP) server over stdio. |

---

## License

Distributed under the MIT License. See `LICENSE` for more information.
