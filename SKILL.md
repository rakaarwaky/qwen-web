---
name: qwen-web
description: Automate Qwen AI Web (chat.qwen.ai) prompt processing via CLI or MCP tools without requiring official API keys.
---
# Qwen Web Automation & MCP Server Skill Guide

Use this skill when an AI agent needs to send prompts or document files to **Qwen AI (`chat.qwen.ai`)** and receive generated AI responses via MCP tools or CLI execution.

---

## Available MCP Tools

| MCP Tool Name         | Description                                  | Key Parameters                                                                    |
| :---------------------- | :--------------------------------------------- | :---------------------------------------------------------------------------------- |
| `qwen_send_prompt`    | Send direct prompt text string to Qwen AI    | `prompt` (str), `timeout_sec` (int, default 120), `headless` (bool, default true) |
| `qwen_process_single` | Process a single Markdown prompt file        | `input_file` (str), `output_file` (optional str), `headless` (bool)               |
| `qwen_process_batch`  | Process an entire directory of prompt files  | `input_dir` (optional str), `output_dir` (optional str), `headless` (bool)        |
| `qwen_start_watcher`  | Continuous folder watcher loop for `input/`  | `interval_sec` (int, default 3), `headless` (bool)                                |
| `qwen_setup_session`  | Launch visible browser for manual login      | None                                                                              |
| `qwen_get_audit_log`  | Retrieve execution audit trail JSONL records | `limit` (int, default 20)                                                         |

---

## Usage Guidelines for AI Agents

### Direct Text Queries (`qwen_send_prompt`)

Use for one-shot prompts where text is provided directly.

```json
{
  "prompt": "Analyze the following system architecture and summarize key bottlenecks...",
  "timeout_sec": 120,
  "headless": true
}
```

### File Processing (`qwen_process_single`)

Use when processing an existing Markdown prompt file stored on disk.

```json
{
  "input_file": "input/role-architect/task_001.md",
  "output_file": "output/role-architect/task_001.md"
}
```

### Batch Processing (`qwen_process_batch`)

Use to process all pending files in the input directory at once.

```json
{
  "input_dir": "input/",
  "output_dir": "output/",
  "headless": true
}
```

### Continuous Watcher (`qwen_start_watcher`)

Use for long-running monitoring of the input directory.

```json
{
  "interval_sec": 3,
  "headless": true
}
```

### Session Authentication (`qwen_setup_session`)

If session cookies expire or CAPTCHA is detected, invoke `qwen_setup_session` to launch a visible browser window for manual user login.

### Audit Trail (`qwen_get_audit_log`)

Retrieve recent execution records for debugging or monitoring.

```json
{
  "limit": 20
}
```

---

## Error Handling for Agents

| Exception | Meaning | Agent Action |
| :--- | :--- | :--- |
| `AuthRequiredError` | Session expired or CAPTCHA detected | Call `qwen_setup_session` for re-authentication |
| `NetworkTimeoutError` | Browser network timeout | Retry with increased `timeout_sec` |
| `OutputValidationError` | Response contains error page or CAPTCHA | Retry or check input quality |
| `CircuitBreakerOpenError` | Too many consecutive failures | Wait and retry later |
| `PromptInjectionError` | Text injection failed | Check if Qwen UI has changed |

---

## Session Management

- Session cookies stored in `qwen_session/` (persistent across runs).
- First run requires `--login` or interactive mode for manual authentication.
- Subsequent runs can use `--headless` mode.
- Session health checked automatically before each file processing.
