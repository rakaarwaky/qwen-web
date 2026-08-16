---
name: qwen-web
description: Automate Qwen AI Web (chat.qwen.ai) prompt processing via CLI or MCP tools without requiring official API keys.
---
# Qwen Web Automation & MCP Server Skill Guide

Use this skill when an AI agent needs to send prompts or document files to **Qwen AI (`chat.qwen.ai`)** and receive generated AI responses via CLI subcommands or MCP tools.

---

## Available CLI Subcommands (`qwen-web-cli`)

| Subcommand | Description | Arguments |
| :--- | :--- | :--- |
| `prompt-direct` | Send inline prompt text | `-t, --text "..." [-o, --output-path FILE] [--headless]` |
| `prompt-only` | Send existing prompt file | `-i, --prompt-path FILE [-o, --output-path FILE] [--headless]` |
| `prompt-with-attachment` | Send prompt file with document attachment | `-i, --prompt-path FILE -a, --attachment-path FILE [-o, --output-path FILE] [--headless]` |
| `login` | Launch browser for manual login / session save | `[--headless]` |
| `init` | Initialize workspace (.agents/skills symlinks) | `[--dir TARGET_DIR]` |
| `mcp` | Run as Model Context Protocol (MCP) server over stdio | None |

### CLI Usage Examples

```bash
# Direct inline prompt
qwen-web-cli prompt-direct -t "<prompt_text>" -o "<output_file.md>" --headless

# Process a prompt file
qwen-web-cli prompt-only -i "<prompt_file.md>" -o "<output_file.md>" --headless

# Process a prompt file with document attachment
qwen-web-cli prompt-with-attachment -i "<prompt_file.md>" -a "<attachment_file>" -o "<output_file.md>" --headless

# Authenticate / Login session
qwen-web-cli login
```

---

## Available MCP Tools

| MCP Tool Name | Description | Key Parameters |
| :--- | :--- | :--- |
| `process_direct_prompt` | Process a direct text prompt string | `prompt` (str), `timeout_sec` (int, default 120), `headless` (bool, default true) |
| `process_prompt_file_only` | Process a single Markdown prompt file | `input_file` (str), `output_file` (optional str), `headless` (bool) |
| `process_prompt_with_attachment` | Process a prompt file with a document attachment | `prompt_file` (str), `attachment_file` (str), `output_file` (optional str), `headless` (bool) |
| `setup_session` | Launch browser for manual login | None |

### MCP JSON Examples

#### Direct Text Query (`process_direct_prompt`)
```json
{
  "prompt": "<your_prompt_text>",
  "timeout_sec": 120,
  "headless": true
}
```

#### File Processing (`process_prompt_file_only`)
```json
{
  "input_file": "<path_to_prompt_file.md>",
  "output_file": "<path_to_output_file.md>"
}
```

#### File Processing With Attachment (`process_prompt_with_attachment`)
```json
{
  "prompt_file": "<path_to_prompt_file.md>",
  "attachment_file": "<path_to_attachment_file>",
  "output_file": "<path_to_output_file.md>"
}
```

---

## Session Management

- Session cookies are stored in `qwen_session/` or `.qwen-web/`.
- If a session expires or CAPTCHA is encountered, run `qwen-web-cli login` or invoke `setup_session` to re-authenticate manually in browser.
