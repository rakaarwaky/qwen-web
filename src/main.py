#!/usr/bin/env python3
"""
qwen-cli v4: Production-grade automation for chat.qwen.ai.
Main execution entrypoint and CLI argument parser.
"""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Any, Literal

from .config import (
    BASE_DIR,
    CHAT_URL,
    DEFAULT_DONE,
    DEFAULT_FAILED,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_PROC,
    DEFAULT_SESSION,
    DEFAULT_TODO,
    AppConfig,
    RunContext,
)
from .browser import browser_session
from .linux import SingleInstanceLock, GracefulShutdown, sd_notify_stop
from .observability import (
    bind_run_context,
    exit_code_for,
    get_logger,
    setup_observability,
    start_span,
    StatusFileWriter,
)
from .qwen_client import QwenClient
from .pipeline import (
    AuditLog,
    _iter_todo,
    _list_input_files,
    _process_file,
)

log = get_logger()


def _run_manual_login(cfg: AppConfig) -> None:
    login_cfg = AppConfig(
        mode="login",
        input_path=cfg.input_path,
        output_path=cfg.output_path,
        done_path=cfg.done_path,
        failed_path=cfg.failed_path,
        proc_path=cfg.proc_path,
        session_path=cfg.session_path,
        log_path=cfg.log_path,
        interval=cfg.interval,
        timeout=cfg.timeout,
        headless=False,
    )
    print(f"\n🔑 [Manual Login] Launching visible browser window on {CHAT_URL}...")
    with browser_session(login_cfg) as bctx:
        page = bctx.pages[0] if bctx.pages else bctx.new_page()
        page.goto(CHAT_URL, wait_until="domcontentloaded")
        print("👉 Please log in or resolve CAPTCHA in the browser window.")
        input("👉 Press [ENTER] here once you have finished logging in: ")
        print(f"✅ Session data successfully saved to '{login_cfg.session_path}'. You can now run in headless mode!\n")


def _interactive_prompt() -> AppConfig:
    print("\n╭─ qwen-cli interactive setup ─────────────────────╮")
    print("│ 1. Watcher Mode (continuous)                     │")
    print("│ 2. Batch Mode (folder)                           │")
    print("│ 3. Single File Mode                              │")
    print("│ 4. Manual Login / Session Setup                  │")
    print("│ 5. Exit                                          │")
    print("╰──────────────────────────────────────────────────╯")
    
    choice = input("Select [1-5, default=1]: ").strip() or "1"
    if choice == "5":
        print("Goodbye!")
        sys.exit(0)
    
    if choice == "4":
        return AppConfig(
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
    
    headless = input("Run headless? [y/N, default=N]: ").strip().lower() == "y"
    mode: str = {"1": "watcher", "2": "batch", "3": "single"}.get(choice, "watcher")
    
    if mode == "single":
        available_files = _list_input_files(DEFAULT_TODO)
        if available_files:
            print("\n📁 Available input files:")
            for idx, (abs_p, rel_p) in enumerate(available_files, 1):
                print(f"  {idx}. {rel_p}")
            
            file_choice = input(f"Select input file [1-{len(available_files)}, default=1]: ").strip() or "1"
            try:
                choice_idx = int(file_choice) - 1
                if 0 <= choice_idx < len(available_files):
                    chosen_abs, chosen_rel = available_files[choice_idx]
                else:
                    chosen_abs, chosen_rel = available_files[0]
            except ValueError:
                chosen_abs, chosen_rel = available_files[0]
            
            return AppConfig(
                mode=mode,
                input_path=chosen_abs,
                output_path=DEFAULT_OUTPUT / chosen_rel,
                done_path=DEFAULT_DONE,
                failed_path=DEFAULT_FAILED,
                proc_path=DEFAULT_PROC,
                session_path=DEFAULT_SESSION,
                log_path=DEFAULT_LOG,
                headless=headless,
            )
        else:
            input_file = input("Enter input file path [default: input.md]: ").strip() or "input.md"
            output_file = input("Enter output file path [default: output.md]: ").strip() or "output.md"
            return AppConfig(
                mode=mode,
                input_path=Path(input_file),
                output_path=Path(output_file),
                done_path=DEFAULT_DONE,
                failed_path=DEFAULT_FAILED,
                proc_path=DEFAULT_PROC,
                session_path=DEFAULT_SESSION,
                log_path=DEFAULT_LOG,
                headless=headless,
            )
    
    return AppConfig(
        mode=mode,
        input_path=DEFAULT_TODO,
        output_path=DEFAULT_OUTPUT,
        done_path=DEFAULT_DONE,
        failed_path=DEFAULT_FAILED,
        proc_path=DEFAULT_PROC,
        session_path=DEFAULT_SESSION,
        log_path=DEFAULT_LOG,
        headless=headless,
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="qwen-cli", description="Automate chat.qwen.ai")
    p.add_argument("-i", "--input", default=str(DEFAULT_TODO))
    p.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT))
    p.add_argument("-d", "--done-dir", default=str(DEFAULT_DONE))
    p.add_argument("--failed-dir", default=str(DEFAULT_FAILED))
    p.add_argument("--proc-dir", default=str(DEFAULT_PROC))
    p.add_argument("--log-dir", default=str(DEFAULT_LOG))
    p.add_argument("-w", "--watch", action="store_true")
    p.add_argument("--interval", type=int, default=3)
    p.add_argument("--headless", action="store_true", help="Run browser headlessly (default: show window)")
    p.add_argument("--data-dir", default=str(DEFAULT_SESSION))
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--login", action="store_true", help="Open browser to log in manually and save session")
    p.add_argument("--mcp", action="store_true", help="Run as Model Context Protocol (MCP) server over stdio")
    # P2: request / polling timeouts
    p.add_argument("--request-timeout", type=int, default=120, help="Max seconds to wait for Qwen response")
    p.add_argument("--poll-interval", type=float, default=1.0, help="Seconds between message-poll checks")
    p.add_argument("--streaming-timeout", type=int, default=180, help="Max seconds for streaming generation")
    # P2: rate limiting
    p.add_argument("--rate-limit", type=int, default=60, help="Max requests per minute")
    # P2: circuit breaker
    p.add_argument("--cb-threshold", type=int, default=5, help="Consecutive failures to trip circuit breaker")
    p.add_argument("--cb-window", type=int, default=30, help="Circuit breaker sliding window in seconds")
    # P6: retry-failed mode
    p.add_argument("--retry-failed", action="store_true", help="Process files in failed/ directory on next run")
    return p.parse_args()


def _build_config(args: argparse.Namespace) -> AppConfig:
    mode_val = "login" if getattr(args, "login", False) else ("watcher" if getattr(args, "watch", False) else None)
    if mode_val is None:
        input_path = Path(args.input)
        mode_val = "batch" if (input_path.is_dir() or not input_path.suffix) else "single"
    return AppConfig(
        mode=mode_val,
        input_path=Path(args.input),
        output_path=Path(args.output),
        done_path=Path(args.done_dir),
        failed_path=Path(args.failed_dir),
        proc_path=Path(args.proc_dir),
        session_path=Path(getattr(args, "data_dir", str(DEFAULT_SESSION))),
        log_path=Path(getattr(args, "log_dir", str(DEFAULT_LOG))),
        interval=getattr(args, "interval", 3),
        timeout=getattr(args, "timeout", 300),
        headless=bool(getattr(args, "headless", False)),
        request_timeout=getattr(args, "request_timeout", 120),
        poll_interval=float(getattr(args, "poll_interval", 1.0)),
        streaming_timeout=getattr(args, "streaming_timeout", 180),
        rate_limit_per_minute=getattr(args, "rate_limit", 60),
        circuit_breaker_threshold=getattr(args, "cb_threshold", 5),
        circuit_breaker_window=getattr(args, "cb_window", 30),
        retry_failed=bool(getattr(args, "retry_failed", False)),
    )


def _run_watcher(client: QwenClient, cfg: AppConfig, audit: AuditLog) -> None:
    """Watcher loop with graceful shutdown support.

    Reads from input/, processes each file via QwenClient, writes output,
    and moves processed files to done/ or failed/. Exits cleanly on SIGINT/SIGTERM.
    """
    ctx = RunContext()
    bind_run_context(run_id=ctx.run_id, mode=cfg.mode, headless=cfg.headless)
    status_writer = StatusFileWriter(cfg.status_path)
    status_writer.write("running", cfg.mode, cfg.headless, ctx.run_id)

    files_processed = 0
    files_failed = 0
    t0 = time.time()

    try:
        for proc_file, rel_path in _iter_todo(cfg):
            if _shutdown_requested():
                log.info("watcher_shutdown_requested")
                break

            try:
                _process_file(client, proc_file, rel_path, cfg, audit, ctx)
                files_processed += 1
            except Exception as e:
                files_failed += 1
                log.error("file_failed", file=str(rel_path), error=str(e))

            status_writer.write(
                "running", cfg.mode, cfg.headless, ctx.run_id,
                cpu_sec=time.time() - t0,
                files_processed=files_processed,
                files_failed=files_failed,
            )
    except Exception as e:
        log.exception("watcher_error", error=str(e))
        status_writer.write(
            "error", cfg.mode, cfg.headless, ctx.run_id,
            error=str(e),
            cpu_sec=time.time() - t0,
            files_processed=files_processed,
            files_failed=files_failed,
        )

    status_writer.write(
        "completed", cfg.mode, cfg.headless, ctx.run_id,
        cpu_sec=time.time() - t0,
        files_processed=files_processed,
        files_failed=files_failed,
    )


# ─── Global shutdown flag (for watcher signal handlers) ──────────────────────
_shutdown_flag: bool = False


def _shutdown_requested() -> bool:
    """Check if shutdown has been requested."""
    return _shutdown_flag


def _signal_handler(signum: int, frame: Any) -> None:
    """Handle SIGINT/SIGTERM for graceful watcher shutdown."""
    global _shutdown_flag
    _shutdown_flag = True


def main() -> int:
    # Check if MCP server mode requested
    args = _parse_args() if len(sys.argv) > 1 else None
    if args and getattr(args, "mcp", False):
        try:
            from .mcp_server import run_mcp_server as _run_mcp
        except ImportError:
            from mcp_server import run_mcp_server as _run_mcp  # type: ignore[import-not-found]
        _run_mcp()
        return 0

    cfg = _interactive_prompt() if len(sys.argv) == 1 else _build_config(args)

    # ── Single-instance lock (P1) ──────────────────────────────────────────
    try:
        with SingleInstanceLock():
            pass
    except Exception as e:
        print(f"⚠️  {e}")
        return 0

    # Observability first: Sentry → OTel → structlog → global exception hooks.
    setup_observability(cfg.log_path)

    if cfg.mode == "login":
        _run_manual_login(cfg)
        return 0

    ctx = RunContext()
    bind_run_context(run_id=ctx.run_id, mode=cfg.mode, headless=cfg.headless)
    audit = AuditLog(cfg.log_path)

    with start_span("qwen-cli.run") as span:
        if span is not None:
            span.set_attribute("mode", cfg.mode)
            span.set_attribute("run_id", ctx.run_id)
            span.set_attribute("headless", cfg.headless)

        # Install signal handlers for graceful watcher shutdown (P4)
        original_sigint = signal.signal(signal.SIGINT, _signal_handler)
        original_sigterm = signal.signal(signal.SIGTERM, _signal_handler)

        try:
            with browser_session(cfg) as bctx:
                client = QwenClient(bctx, cfg)

                if cfg.mode == "watcher":
                    _run_watcher(client, cfg, audit)
                else:
                    # batch / single mode: same loop as before
                    for proc_file, rel_path in _iter_todo(cfg):
                        _process_file(client, proc_file, rel_path, cfg, audit, ctx)
        except Exception as e:
            log.exception("run_failed", error_type=type(e).__name__, error=str(e))
            return exit_code_for(e)
        finally:
            # Restore original signal handlers
            try:
                if original_sigint is not None:
                    signal.signal(signal.SIGINT, original_sigint)
                if original_sigterm is not None:
                    signal.signal(signal.SIGTERM, original_sigterm)
            except (OSError, ValueError):
                pass

            # Notify systemd of graceful stop (P1)
            sd_notify_stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
