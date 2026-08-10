"""MCP Server entrypoint for qwen-web-automation.

Exposes 1:1 CLI features as Model Context Protocol (MCP) tools:
  - qwen_send_prompt: Send direct text prompt to chat.qwen.ai
  - qwen_process_single: Single file processing mode
  - qwen_process_batch: Batch directory processing mode
  - qwen_start_watcher: Folder watcher mode
  - qwen_setup_session: Manual login / browser session setup
  - qwen_get_audit_log: Read execution audit history JSONL log
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from fastmcp import FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = None

if not __package__:
    _src_dir = Path(__file__).resolve().parent
    _parent_dir = _src_dir.parent
    if str(_parent_dir) not in sys.path:
        sys.path.insert(0, str(_parent_dir))
    __package__ = _src_dir.name

from .browser import browser_session
from .observability import get_logger, setup_observability
from .pipeline import AuditLog, _iter_todo, _process_file, _watcher_sleep
from .qwen_client import QwenClient
from .types import (
    CHAT_URL,
    DEFAULT_DONE,
    DEFAULT_FAILED,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_PROC,
    DEFAULT_SESSION,
    DEFAULT_TODO,
    AppConfig,
    AuthRequiredError,
    RunContext,
)

# Initialize observability stack with stderr logging
setup_observability(DEFAULT_LOG)
log = get_logger("mcp_server")

# Initialize FastMCP application instance
mcp = FastMCP("Qwen-Web") if FastMCP is not None else None


def _get_mcp_app() -> Any:
    """Return FastMCP app instance or raise ImportError if mcp package is missing."""
    if mcp is None:
        raise ImportError(
            "The 'mcp' Python package is required to run the MCP server. Install it via 'pip install mcp'."
        )
    return mcp


def _isolate_thread_event_loop() -> None:
    """Ensure worker thread has an isolated event loop for Playwright sync_api compatibility."""
    import asyncio
    try:
        if hasattr(asyncio, "_set_running_loop"):
            asyncio._set_running_loop(None)
    except Exception:
        pass
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception:
        pass


def _register_tool(fn: Any) -> Any:
    """Register a function as an MCP tool if FastMCP is available.

    Wraps the function with mcp.tool() decorator when the 'mcp' package is installed.
    Returns the function unchanged when mcp is unavailable (graceful degradation).

    Args:
        fn: Async function to register as an MCP tool.

    Returns:
        Decorated function (MCP tool) or the original function if mcp is missing.

    """
    if mcp is not None:
        return mcp.tool()(fn)
    return fn


@_register_tool
async def qwen_send_prompt(
    prompt: str,
    timeout_sec: int = 120,
    headless: bool = True,
) -> str:
    """Send a direct text prompt string to chat.qwen.ai and return AI answer."""
    def _sync_op() -> str:
        _isolate_thread_event_loop()

        cfg = AppConfig(
            mode="single",
            input_path=DEFAULT_TODO,
            output_path=DEFAULT_OUTPUT,
            done_path=DEFAULT_DONE,
            failed_path=DEFAULT_FAILED,
            proc_path=DEFAULT_PROC,
            session_path=DEFAULT_SESSION,
            log_path=DEFAULT_LOG,
            timeout=timeout_sec,
            headless=headless,
        )

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write(prompt)
            tmp_path = Path(tmp.name)

        try:
            with browser_session(cfg) as bctx:
                client = QwenClient(bctx, cfg)
                response = client.send_file(filepath=tmp_path, timeout_sec=timeout_sec)
                return response
        except AuthRequiredError as e:
            return f"ERROR [AUTH_REQUIRED]: {e}"
        except Exception as e:
            return f"ERROR [{type(e).__name__}]: {e}"
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    return await asyncio.to_thread(_sync_op)


@_register_tool
async def qwen_process_single(
    input_file: str,
    output_file: str | None = None,
    headless: bool = True,
) -> str:
    """Process a single Markdown prompt file (1:1 CLI Single File Mode)."""
    def _sync_op() -> str:
        _isolate_thread_event_loop()
        in_p = Path(input_file).resolve()
        if not in_p.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        out_p = Path(output_file).resolve() if output_file else DEFAULT_OUTPUT / in_p.name

        cfg = AppConfig(
            mode="single",
            input_path=in_p,
            output_path=out_p,
            done_path=DEFAULT_DONE,
            failed_path=DEFAULT_FAILED,
            proc_path=DEFAULT_PROC,
            session_path=DEFAULT_SESSION,
            log_path=DEFAULT_LOG,
            headless=headless,
        )

        audit_log = AuditLog(cfg.log_path)
        ctx = RunContext()

        try:
            proc_file = cfg.proc_path / in_p.name
            proc_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(in_p, proc_file)

            with browser_session(cfg) as bctx:
                client = QwenClient(bctx, cfg)
                _process_file(client, proc_file, Path(in_p.name), cfg, audit_log, ctx)
                return f"Successfully processed {in_p.name} -> {out_p}"
        except AuthRequiredError as e:
            return f"ERROR [AUTH_REQUIRED]: {e}"
        except Exception as e:
            return f"ERROR [{type(e).__name__}]: {e}"

    return await asyncio.to_thread(_sync_op)


@_register_tool
async def qwen_process_batch(
    input_dir: str | None = None,
    output_dir: str | None = None,
    headless: bool = True,
) -> str:
    """Process all prompt files inside an input directory (1:1 CLI Batch Mode)."""
    def _sync_op() -> str:
        _isolate_thread_event_loop()
        in_p = Path(input_dir).resolve() if input_dir else DEFAULT_TODO
        out_p = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT

        cfg = AppConfig(
            mode="batch",
            input_path=in_p,
            output_path=out_p,
            done_path=DEFAULT_DONE,
            failed_path=DEFAULT_FAILED,
            proc_path=DEFAULT_PROC,
            session_path=DEFAULT_SESSION,
            log_path=DEFAULT_LOG,
            headless=headless,
        )

        audit_log = AuditLog(cfg.log_path)
        ctx = RunContext()
        processed = 0
        failed = 0

        try:
            with browser_session(cfg) as bctx:
                client = QwenClient(bctx, cfg)
                for proc_file, rel_path in _iter_todo(cfg):
                    try:
                        _process_file(client, proc_file, rel_path, cfg, audit_log, ctx)
                        processed += 1
                    except Exception as e:
                        failed += 1
                        log.error("batch_file_failed", file=str(rel_path), error=str(e))

            return f"Batch processing complete. Successfully processed: {processed}, Failed: {failed}"
        except AuthRequiredError as e:
            return f"ERROR [AUTH_REQUIRED]: {e}"
        except Exception as e:
            return f"ERROR [{type(e).__name__}]: {e}"

    return await asyncio.to_thread(_sync_op)


@_register_tool
async def qwen_start_watcher(interval_sec: int = 3, headless: bool = True) -> str:
    """Run folder watcher loop to continuously monitor input/ for new files (1:1 CLI Watcher Mode)."""
    def _sync_op() -> str:
        _isolate_thread_event_loop()
        cfg = AppConfig(
            mode="watcher",
            input_path=DEFAULT_TODO,
            output_path=DEFAULT_OUTPUT,
            done_path=DEFAULT_DONE,
            failed_path=DEFAULT_FAILED,
            proc_path=DEFAULT_PROC,
            session_path=DEFAULT_SESSION,
            log_path=DEFAULT_LOG,
            interval=interval_sec,
            headless=headless,
        )

        audit_log = AuditLog(cfg.log_path)
        ctx = RunContext()

        try:
            with browser_session(cfg) as bctx:
                client = QwenClient(bctx, cfg)
                for proc_file, rel_path in _iter_todo(cfg):
                    _process_file(client, proc_file, rel_path, cfg, audit_log, ctx)
                    _watcher_sleep(cfg.interval)

            return "Watcher loop completed."
        except AuthRequiredError as e:
            return f"ERROR [AUTH_REQUIRED]: {e}"
        except Exception as e:
            return f"ERROR [{type(e).__name__}]: {e}"

    return await asyncio.to_thread(_sync_op)


@_register_tool
async def qwen_setup_session() -> str:
    """Launch visible browser on chat.qwen.ai for manual login / session setup (1:1 CLI Login Mode)."""
    def _sync_op() -> str:
        _isolate_thread_event_loop()
        cfg = AppConfig(
            mode="login",
            input_path=DEFAULT_TODO,
            output_path=DEFAULT_OUTPUT,
            done_path=DEFAULT_DONE,
            failed_path=DEFAULT_FAILED,
            proc_path=DEFAULT_PROC,
            session_path=DEFAULT_SESSION,
            log_path=DEFAULT_LOG,
            headless=False,
        )

        with browser_session(cfg) as bctx:
            page = bctx.pages[0] if bctx.pages else bctx.new_page()
            page.goto(CHAT_URL, wait_until="domcontentloaded")
            log.info("Manual login browser page opened successfully")

        return f"Browser session saved to '{cfg.session_path}'. You can now run tasks in headless mode."

    return await asyncio.to_thread(_sync_op)


@_register_tool
def qwen_get_audit_log(limit: int = 20) -> str:
    """Fetch latest entries from the JSONL audit trail log."""
    audit_file = DEFAULT_LOG / "audit_history.jsonl"
    if not audit_file.exists():
        return "Audit log file does not exist yet."

    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-limit:]
    records: list[Any] = [json.loads(line) for line in recent if line.strip()]
    return json.dumps(records, indent=2)


def run_mcp_server() -> None:
    """Run the FastMCP server over stdio."""
    # Redirect standard text prints & logging to stderr to protect JSON-RPC stdio
    sys.stdout = sys.stderr

    setup_observability(DEFAULT_LOG)
    log.info("Starting Qwen Web Automation MCP Server...")

    # Restore sys.stdout to sys.__stdout__ (FD 1) for FastMCP stdio transport
    sys.stdout = sys.__stdout__
    app = _get_mcp_app()
    app.run()


if __name__ == "__main__":
    run_mcp_server()
