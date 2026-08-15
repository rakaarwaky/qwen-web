"""qwen-cli v4: Production-grade automation for chat.qwen.ai.

Root layer: CLI entry point — argument parsing, validation, lifecycle guards,
and dispatch to the CLI surface commands via the auto-wired DI container.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

import modules.cli.src.surface_cli_init_command as surface_cli_init_command
import modules.cli.src.surface_cli_interactive_controller as surface_cli_interactive_controller
import modules.cli.src.surface_cli_login_command as surface_cli_login_command
import modules.cli.src.surface_cli_run_command as surface_cli_run_command
from modules.core.src.root_core_container import SharedContainer
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_SESSION,
)
from modules.shared.src.taxonomy_core_error import SingleInstanceError

_ERROR_PREFIX = "[ERROR]"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for qwen-cli subcommands and options."""
    p = argparse.ArgumentParser(prog="qwen-cli", description="Automate chat.qwen.ai")
    p.add_argument("command", nargs="?", default=None, help="Subcommand (e.g. init)")
    p.add_argument("target_dir", nargs="?", default=None, help="Target directory for init subcommand")
    p.add_argument(
        "--init",
        action="store_true",
        help="Initialize workspace with .agents/skills and .qwen-web symlinks",
    )
    p.add_argument("--prompt", "-p", dest="prompt", default=None, help="Path to prompt markdown/text file")
    p.add_argument("--file", "-f", dest="file", default=None, help="Path to attachment file to upload")
    p.add_argument("-i", "--input", default=None, help="Legacy input file/directory path")
    p.add_argument("-o", "--output", default=None, help="Output destination file or directory (default: cwd)")
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
    p.add_argument(
        "--inline-prompt",
        action="store_true",
        help="Inject the input file contents as plain text instead of attaching the file to Qwen",
    )
    p.add_argument("--rate-limit", type=int, default=60, help="Max requests per minute")
    p.add_argument("--cb-threshold", type=int, default=5, help="Consecutive failures to trip circuit breaker")
    p.add_argument("--cb-window", type=int, default=30, help="Circuit breaker sliding window in seconds")
    p.add_argument("--retry-failed", action="store_true", help="Process files in failed/ directory on next run")
    return p.parse_args(argv)


def _build_config(args: argparse.Namespace) -> AppConfig:
    """Build and validate AppConfig using explicit CLI precedence.

    Direct single-file mode (`--prompt` and optional `--file`) processes in-place
    without queue moves. Output defaults to current working directory.
    """
    login = bool(getattr(args, "login", False))
    watch = bool(getattr(args, "watch", False))
    prompt_arg = getattr(args, "prompt", None)
    file_arg = getattr(args, "file", None)
    input_arg = getattr(args, "input", None)
    output_arg = getattr(args, "output", None)

    prompt_p = Path(prompt_arg).resolve() if isinstance(prompt_arg, (str, Path)) else None
    file_p = Path(file_arg).resolve() if isinstance(file_arg, (str, Path)) else None

    if prompt_p and not prompt_p.exists():
        raise ValueError(f"Prompt file not found: {prompt_arg}")
    if file_p and not file_p.exists():
        raise ValueError(f"Attachment file not found: {file_arg}")

    dummy_path = Path("/dev/null")
    if login:
        mode_val = "login"
        input_path = prompt_p or dummy_path
    elif prompt_p:
        mode_val = "single"
        input_path = prompt_p
    elif watch:
        input_path = Path(input_arg) if input_arg else dummy_path
        mode_val = "watcher"
    elif input_arg:
        input_path = Path(input_arg)
        mode_val = "batch" if input_path.is_dir() else "single"
    else:
        input_path = dummy_path
        mode_val = "batch"

    # Default output path to output folder (.qwen-web/output or DEFAULT_OUTPUT) when unspecified
    if output_arg:
        out_p = Path(output_arg)
    else:
        local_out = Path.cwd() / ".qwen-web" / "output"
        target_dir = local_out if local_out.exists() else DEFAULT_OUTPUT
        if prompt_p:
            out_p = target_dir / f"{prompt_p.stem}_output.md"
        else:
            out_p = target_dir

    return AppConfig(
        mode=mode_val,
        input_path=input_path,
        output_path=out_p,
        done_path=dummy_path,
        failed_path=dummy_path,
        proc_path=dummy_path,
        session_path=Path(getattr(args, "data_dir", str(DEFAULT_SESSION))),
        log_path=Path(getattr(args, "log_dir", str(DEFAULT_LOG))),
        interval=getattr(args, "interval", 3),
        timeout=getattr(args, "timeout", 300),
        headless=False if login else bool(getattr(args, "headless", False)),
        prompt_file=prompt_p,
        prompt_path=prompt_p,
        file_path=file_p,
        request_timeout=getattr(args, "request_timeout", 120),
        poll_interval=float(getattr(args, "poll_interval", 1.0)),
        streaming_timeout=getattr(args, "streaming_timeout", 180),
        inline_prompt=bool(getattr(args, "inline_prompt", False)),
        rate_limit_per_minute=getattr(args, "rate_limit", 60),
        circuit_breaker_threshold=getattr(args, "cb_threshold", 5),
        circuit_breaker_window=getattr(args, "cb_window", 30),
        retry_failed=bool(getattr(args, "retry_failed", False)),
    )


@lru_cache(maxsize=1)
def _default_container() -> SharedContainer:
    """Build the default auto-wired DI container (cached singleton)."""
    return SharedContainer()


def _result_exit_code(result: dict[str, object]) -> int:
    """Convert a surface response envelope to a CLI exit code."""
    if result.get("success"):
        print(result.get("message", ""))
        return 0
    print(f"{_ERROR_PREFIX} {result.get('error') or 'Unknown error'}", file=sys.stderr)
    return 1


def _run_cli_lifecycle(dispatch: Callable[[SharedContainer], int]) -> int:
    """Own the CLI-only LinuxGuard lifecycle.

    MCP does not call this function and constructs its container with
    ``use_linux_guard=False``. A CLI lock is acquired before dispatch, READY is
    emitted after container initialization, and STOPPING plus lock release are
    guaranteed by the finalizer.
    """
    container = _default_container()
    linux = container.linux
    lock: Any = None
    try:
        if linux is not None:
            lock = linux.acquire_lock()
            linux.sd_notify_ready()
        return dispatch(container)
    finally:
        if linux is not None and lock is not None:
            try:
                linux.sd_notify_stop()
            finally:
                linux.release_lock(lock)


def _dispatch(
    container: SharedContainer,
    raw_argv: list[str],
    args: argparse.Namespace | None,
    cfg: AppConfig | None,
) -> int:
    """Dispatch one already-parsed CLI invocation inside the Linux lifecycle."""
    # Explicit precedence: login wins over init, including --login --init.
    if args is not None and bool(getattr(args, "login", False)):
        if cfg is None:
            print(f"{_ERROR_PREFIX} Missing login configuration.", file=sys.stderr)
            return 1
        return _run_manual_login(cfg, container)

    # Init is an action rather than an AppConfig mode. It wins over watcher
    # and path inference when login is absent.
    if args is not None and (getattr(args, "command", None) == "init" or bool(getattr(args, "init", False))):
        result = surface_cli_init_command.handle(args, container.core)
        return _result_exit_code(result)

    if not raw_argv:
        result = surface_cli_interactive_controller.InteractiveController(container.core).run()
        return _result_exit_code(result)

    if args is None or cfg is None:
        print(f"{_ERROR_PREFIX} Missing CLI configuration.", file=sys.stderr)
        return 1
    args._cfg = cfg
    result = surface_cli_run_command.handle(args, container.core)
    return _result_exit_code(result)


def main(argv: list[str] | None = None) -> int:
    """Run the main entrypoint for qwen-cli."""
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    args = _parse_args(raw_argv) if raw_argv else None

    # MCP is a separate runtime and must never enter the CLI LinuxGuard path.
    if args and getattr(args, "mcp", False):
        from modules.root_mcp_main_entry import run_mcp_server

        run_mcp_server()
        return 0

    cfg: AppConfig | None = None
    if args is not None:
        is_init = getattr(args, "command", None) == "init" or bool(getattr(args, "init", False))
        if not is_init or bool(getattr(args, "login", False)):
            try:
                cfg = _build_config(args)
            except (OSError, ValueError) as exc:
                print(f"{_ERROR_PREFIX} {exc}", file=sys.stderr)
                return 1

    try:
        return _run_cli_lifecycle(lambda container: _dispatch(container, raw_argv, args, cfg))
    except SingleInstanceError as exc:
        print(f"{_ERROR_PREFIX} {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # boundary: user-facing error after lifecycle cleanup
        print(f"{_ERROR_PREFIX} {exc}", file=sys.stderr)
        return 1


def _interactive_prompt(core: Any | None = None) -> AppConfig | None:
    """Display the interactive menu and build AppConfig from user selections."""
    if core is None:
        core = _default_container().core
    return surface_cli_interactive_controller.InteractiveController(core).interactive_prompt()


def _run_manual_login(cfg: AppConfig, container: SharedContainer | None = None) -> int:
    """Launch visible browser for interactive login."""
    if container is None:
        container = _default_container()
    result = surface_cli_login_command.handle(None, container.core, cfg)
    return _result_exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
