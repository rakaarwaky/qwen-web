#!/usr/bin/env python3
"""qwen-cli v4: Production-grade automation for chat.qwen.ai.

Root layer: CLI entry point — argparse parsing, config building, and dispatch
to the CLI surface commands via the auto-wired DI container.
"""

from __future__ import annotations

import argparse
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from modules.cli.src import (
    surface_cli_init_command,
    surface_cli_interactive_controller,
    surface_cli_login_command,
    surface_cli_run_command,
)
from modules.core.src.root_core_container import SharedContainer
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_DONE,
    DEFAULT_FAILED,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_PROC,
    DEFAULT_SESSION,
    DEFAULT_TODO,
)
from modules.shared.src.taxonomy_core_vo import RunContext


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for qwen-cli subcommands and options."""
    p = argparse.ArgumentParser(prog="qwen-cli", description="Automate chat.qwen.ai")
    p.add_argument("command", nargs="?", default=None, help="Subcommand (e.g. init)")
    p.add_argument("target_dir", nargs="?", default=None, help="Target directory for init subcommand")
    p.add_argument("--init", action="store_true", help="Initialize workspace with .agents/skills and .qwen-web symlinks")
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
    p.add_argument("--request-timeout", type=int, default=120, help="Max seconds to wait for Qwen response")
    p.add_argument("--poll-interval", type=float, default=1.0, help="Seconds between message-poll checks")
    p.add_argument("--streaming-timeout", type=int, default=180, help="Max seconds for streaming generation")
    p.add_argument("--rate-limit", type=int, default=60, help="Max requests per minute")
    p.add_argument("--cb-threshold", type=int, default=5, help="Consecutive failures to trip circuit breaker")
    p.add_argument("--cb-window", type=int, default=30, help="Circuit breaker sliding window in seconds")
    p.add_argument("--retry-failed", action="store_true", help="Process files in failed/ directory on next run")
    return p.parse_args()


def _build_config(args: argparse.Namespace) -> AppConfig:
    """Build AppConfig from parsed CLI arguments."""
    if args.login:
        mode_val: str = "login"
    elif args.watch:
        mode_val = "watcher"
    else:
        input_path = Path(args.input)
        mode_val = "batch" if (input_path.is_dir() or not input_path.suffix) else "single"
    return AppConfig(
        mode=mode_val,
        input_path=Path(args.input),
        output_path=Path(args.output),
        done_path=Path(getattr(args, "done_dir", str(DEFAULT_DONE))),
        failed_path=Path(getattr(args, "failed_dir", str(DEFAULT_FAILED))),
        proc_path=Path(getattr(args, "proc_dir", str(DEFAULT_PROC))),
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


@lru_cache(maxsize=1)
def _default_container() -> SharedContainer:
    """Build the default auto-wired DI container (cached singleton)."""
    return SharedContainer()


def main(argv: list[str] | None = None) -> int:
    """Run the main entrypoint for qwen-cli."""
    args = _parse_args() if (argv is not None or len(sys.argv) > 1) else None

    # MCP server mode
    if args and getattr(args, "mcp", False):
        from modules.root_mcp_main_entry import run_mcp_server
        run_mcp_server()
        return 0

    # Init subcommand
    if args and (getattr(args, "command", None) == "init" or getattr(args, "init", False)):
        container = _default_container()
        result = surface_cli_init_command.handle(args, container.core)
        return 0 if result.get("success") else 1

    # Interactive mode when no args
    if len(sys.argv) == 1 and argv is None:
        cfg = _interactive_prompt()
        if cfg is None:
            return 0
    else:
        if args is None:
            print("ERROR: missing CLI arguments", file=sys.stderr)
            return 1
        cfg = _build_config(args)

    # Observability first
    try:
        container = _default_container()
    except Exception:
        print("[ERROR] Failed to initialize qwen-web. Run 'qwen-web-cli init' first.", file=sys.stderr)
        return 1

    if cfg.mode == "login":
        _run_manual_login(cfg)
        return 0

    args_with_cfg = args
    if args_with_cfg is not None:
        args_with_cfg._cfg = cfg
    result = surface_cli_run_command.handle(args_with_cfg, container.core)
    if not result.get("success"):
        print(result.get("error", "Unknown error"), file=sys.stderr)
        return 1
    return 0


def _interactive_prompt() -> AppConfig | None:
    """Display interactive TUI menu and build AppConfig from user selections."""
    container = _default_container()
    return surface_cli_interactive_controller.InteractiveController(container.core).interactive_prompt()


def _run_manual_login(cfg: AppConfig) -> None:
    """Launch visible browser for interactive login (TTY flow in the surface)."""
    container = _default_container()
    surface_cli_login_command.handle(None, container.core, cfg)


if __name__ == "__main__":
    sys.exit(main())
