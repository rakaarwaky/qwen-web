# Agent Instructions

<!-- lean-ctx -->
## lean-ctx

lean-ctx is active — the MCP tools replace native equivalents.
Full rules: LEAN-CTX.md (open on demand — do not auto-load).
<!-- /lean-ctx -->

---

## Project Context

`qwen-web` is a Playwright-based automation tool for Qwen AI (`chat.qwen.ai`). It processes Markdown prompt files through a browser session without requiring API keys.

### Module Architecture

| Module | Purpose | Complexity |
|--------|---------|------------|
| `src/main.py` | CLI entrypoint, argument parser, interactive TUI | cc=28 |
| `src/browser.py` | Playwright session management, health checks | cc=29 |
| `src/pipeline.py` | File pipeline: watcher, batch, single file, retry | cc=19 |
| `src/qwen_client.py` | Core automation orchestrator | cc=21 |
| `src/prompt_injector.py` | DOM text injection (React setter + clipboard) | cc=32 |
| `src/sender.py` | Send button click, message counting | cc=23 |
| `src/streamer.py` | Response streaming detection & validation | cc=35 |
| `src/saver.py` | Output file writing with metadata | — |
| `src/types.py` | Type definitions, AppConfig, exceptions | — |
| `src/observability.py` | structlog, OTel, Sentry setup | — |
| `src/mcp_server.py` | MCP Server (1:1 CLI features) | — |
| `src/file_uploader.py` | File attachment upload | — |

### Code Health

- **Navigability**: 81/100
- **Functions over CC>15**: 11
- **Worst complexity**: 80 (tests/manual_probe.py:61)

### Key Patterns

1. **Exception hierarchy**: Base `QwenCliError` with domain-specific subclasses (`AuthRequiredError`, `NetworkTimeoutError`, `OutputValidationError`, etc.)
2. **Module decomposition**: Large files split into focused modules (`prompt_injector.py`, `sender.py`, `streamer.py`, `saver.py`)
3. **Centralized types**: `AppConfig`, `CircuitBreaker`, `RateLimiter`, `LifecycleEmitter` in `types.py`
4. **XDG compliance**: Paths follow XDG Base Directory Specification

### Testing

- **Behavior lock**: `tests/test_qwen_client_behavior.py` — DOM selectors & injection strategies
- **Pipeline fixtures**: `tests/test_pipeline_fixtures.py` — file state management
- **E2E**: `tests/test_e2e_pipeline.py` — live network tests (excluded from CI)

Run: `pytest tests/ -v`

### Common Commands

```bash
# Development
pytest tests/test_qwen_client_behavior.py -v    # Behavior lock
pytest tests/ -v                                  # Full suite

# Production
python3 src/main.py --watch --headless           # Watcher mode
python3 src/main.py -i input -o output --headless # Batch mode
python3 src/main.py --mcp                        # MCP server
python3 src/main.py --login                      # Manual login
```
