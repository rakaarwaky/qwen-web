#!/usr/bin/env python3
"""qwen-cli v4: Production-grade automation for chat.qwen.ai.

Main execution entrypoint and CLI argument parser.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Literal

if not __package__:
    _src_dir = Path(__file__).resolve().parent
    _parent_dir = _src_dir.parent
    if str(_parent_dir) not in sys.path:
        sys.path.insert(0, str(_parent_dir))
    __package__ = _src_dir.name

from .browser import browser_session
from .linux import SingleInstanceLock, sd_notify_stop
from .observability import (
    StatusFileWriter,
    bind_run_context,
    exit_code_for,
    get_logger,
    setup_observability,
    start_span,
)
from .pipeline import (
    AuditLog,
    _iter_todo,
    _list_input_files,
    _process_file,
    is_watcher_shutdown_set,
)
from .qwen_client import QwenClient
from .types import (
    BASE_DIR,
    CHAT_URL,
    DEFAULT_DONE,
    DEFAULT_FAILED,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_PROC,
    DEFAULT_SESSION,
    DEFAULT_TODO,
    XDG_SKILL_MD,
    AppConfig,
    AuthRequiredError,
    RunContext,
)

log = get_logger()

# ─── Centralized Default Paths (DRY) ─────────────────────────────────────────
DEFAULT_PATHS: dict[str, Any] = {
    "input_path": DEFAULT_TODO,
    "output_path": DEFAULT_OUTPUT,
    "done_path": DEFAULT_DONE,
    "failed_path": DEFAULT_FAILED,
    "proc_path": DEFAULT_PROC,
    "session_path": DEFAULT_SESSION,
    "log_path": DEFAULT_LOG,
}


def run_init(target_dir: Path | str = ".") -> None:
    """Initialize workspace with .agents/skills/qwen-web/SKILL.md, .qwen-web symlinks to XDG paths, and .gitignore entry."""
    target_path = Path(target_dir).resolve()
    print(f"\n[INIT] Initializing qwen-web environment in: {target_path}\n")

    # 1. Ensure XDG directories exist
    DEFAULT_TODO.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
    DEFAULT_LOG.mkdir(parents=True, exist_ok=True)

    # 2. Create .agents/skills/qwen-web/SKILL.md
    skills_dir = target_path / ".agents" / "skills" / "qwen-web"
    skills_dir.mkdir(parents=True, exist_ok=True)
    skill_md_dest = skills_dir / "SKILL.md"

    pkg_skill_md = BASE_DIR / "SKILL.md"
    if XDG_SKILL_MD.exists():
        shutil.copy2(XDG_SKILL_MD, skill_md_dest)
    elif pkg_skill_md.exists():
        shutil.copy2(pkg_skill_md, skill_md_dest)
    else:
        skill_content = (
            "---\n"
            "name: qwen-web\n"
            "description: Automate Qwen AI Web (chat.qwen.ai) prompt processing via CLI or MCP tools.\n"
            "---\n"
            "# Qwen Web Automation Skill Guide\n"
        )
        skill_md_dest.write_text(skill_content, encoding="utf-8")

    try:
        rel_skill = skill_md_dest.relative_to(target_path)
    except ValueError:
        rel_skill = skill_md_dest
    print(f"  [OK] Created skill definition: {rel_skill}")

    # 3. Create .qwen-web directory with symlinks to XDG paths
    dot_qwen = target_path / ".qwen-web"
    dot_qwen.mkdir(parents=True, exist_ok=True)

    links = {
        "log": DEFAULT_LOG,
        "input": DEFAULT_TODO,
        "output": DEFAULT_OUTPUT,
    }

    for link_name, xdg_target in links.items():
        link_path = dot_qwen / link_name
        if link_path.is_symlink() or link_path.exists():
            if link_path.is_dir() and not link_path.is_symlink():
                pass
            else:
                link_path.unlink(missing_ok=True)

        if not link_path.exists() and not link_path.is_symlink():
            try:
                os.symlink(xdg_target, link_path, target_is_directory=True)
                print(f"  [LINK] Symlinked .qwen-web/{link_name} -> {xdg_target}")
            except Exception as e:
                print(f"  [WARNING] Could not create symlink .qwen-web/{link_name}: {e}")

    # 4. Add .qwen-web/ to .gitignore
    git_ignore = target_path / ".gitignore"
    entry = ".qwen-web/"
    if git_ignore.exists():
        content = git_ignore.read_text(encoding="utf-8")
        if entry not in content and ".qwen-web" not in content:
            if content and not content.endswith("\n"):
                content += "\n"
            content += f"{entry}\n"
            git_ignore.write_text(content, encoding="utf-8")
            print(f"  [FILE] Added {entry} to existing .gitignore")
        else:
            print(f"  [INFO] {entry} already present in .gitignore")
    else:
        git_ignore.write_text(f"{entry}\n", encoding="utf-8")
        print(f"  [FILE] Created .gitignore with {entry}")

    print("\n[DONE] Workspace initialization complete!\n")


def _run_manual_login(cfg: AppConfig) -> None:
    """Launch visible browser for interactive login and save session cookies.

    Opens chat.qwen.ai in a visible browser window, prompts the user to log in
    manually (including CAPTCHA resolution), and persists the session data to
    cfg.session_path so subsequent headless runs can reuse the authenticated state.

    Args:
        cfg: AppConfig with mode='login' and headless=False.

    Raises:
        SystemExit: If stdin is not a TTY (interactive terminal required).

    """
    if not sys.stdin.isatty():
        print("[ERROR] Manual login requires an interactive terminal (TTY).", file=sys.stderr)
        sys.exit(1)

    login_cfg = AppConfig(
        mode="login",
        **DEFAULT_PATHS,
        interval=cfg.interval,
        timeout=cfg.timeout,
        headless=False,
    )
    print(f"\n[LOGIN] Launching visible browser window on {CHAT_URL}...")
    with browser_session(login_cfg) as bctx:
        page = bctx.pages[0] if bctx.pages else bctx.new_page()
        page.goto(CHAT_URL, wait_until="domcontentloaded")
        print("Please log in or resolve CAPTCHA in the browser window.")
        input("Press [ENTER] here once you have finished logging in: ")
        print(f"[OK] Session data successfully saved to '{login_cfg.session_path}'. You can now run in headless mode!\n")


def _interactive_prompt() -> AppConfig | None:
    """Display interactive TUI menu and build AppConfig from user selections.

    Presents a numbered menu for selecting operation mode (watcher, batch, single,
    login, init, exit), collects headless preference, and resolves input/output
    paths. Returns None if the user selects exit or init.

    Returns:
        AppConfig built from user selections, or None to exit.

    """
    if not sys.stdin.isatty():
        print("[ERROR] Interactive mode requires a TTY. Please provide CLI arguments.", file=sys.stderr)
        return None

    print("\n╭─ qwen-cli interactive setup ─────────────────────╮")
    print("│ 1. Watcher Mode (continuous)                     │")
    print("│ 2. Batch Mode (folder)                           │")
    print("│ 3. Single File Mode                              │")
    print("│ 4. Manual Login / Session Setup                  │")
    print("│ 5. Initialize Workspace (.agents/skills & .qwen) │")
    print("│ 6. Exit                                          │")
    print("╰──────────────────────────────────────────────────╯")
    
    choice = input("Select [1-6, default=1]: ").strip() or "1"
    if choice == "6":
        print("Goodbye!")
        return None
    
    if choice == "5":
        run_init(Path.cwd())
        return None
    
    if choice == "4":
        return AppConfig(
            mode="login",
            **DEFAULT_PATHS,
            headless=False,
        )
    
    headless = input("Run headless? [y/N, default=N]: ").strip().lower() == "y"
    mode_map: dict[str, Literal["watcher", "batch", "single", "login"]] = {
        "1": "watcher",
        "2": "batch",
        "3": "single",
    }
    mode: Literal["watcher", "batch", "single", "login"] = mode_map.get(choice, "watcher")
    
    if mode == "single":
        available_files = _list_input_files(DEFAULT_TODO)
        if available_files:
            print("\n[FILES] Available input files:")
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
                output_path=DEFAULT_OUTPUT,
                **{k: v for k, v in DEFAULT_PATHS.items() if k not in ("input_path", "output_path")},
                headless=headless,
            )
        else:
            input_file = input(f"Enter input file path [default: {DEFAULT_TODO}]: ").strip() or str(DEFAULT_TODO)
            output_file = input(f"Enter output file path [default: {DEFAULT_OUTPUT}]: ").strip() or str(DEFAULT_OUTPUT)
            return AppConfig(
                mode=mode,
                input_path=Path(input_file),
                output_path=Path(output_file),
                **{k: v for k, v in DEFAULT_PATHS.items() if k not in ("input_path", "output_path")},
                headless=headless,
            )
    
    return AppConfig(
        mode=mode,
        **DEFAULT_PATHS,
        headless=headless,
    )


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for qwen-cli subcommands and options.

    Returns:
        argparse.Namespace with all parsed arguments including mode flags,
        path overrides, timeout/rate-limit/circuit-breaker settings, and MCP flag.

    """
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
    """Build AppConfig from parsed CLI arguments.

    Derives the operation mode from flags (--login, --watch, or input path type)
    and maps all CLI arguments to their corresponding AppConfig fields.

    Args:
        args: Parsed argparse.Namespace from _parse_args().

    Returns:
        Fully constructed AppConfig ready for execution.

    """
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
            if is_watcher_shutdown_set():
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


from .pipeline import (
    _install_watcher_signal_handlers,
)


def main() -> int:
    """Run the main entrypoint for qwen-cli.

    Handles argument parsing, mode dispatch (login/watcher/batch/single/MCP/init),
    observability setup, single-instance locking, browser session management, and
    graceful shutdown via signal handlers.

    Returns:
        Process exit code: 0=success, 1=general error, 2=auth required, 130=SIGINT.

    """
    # Check if MCP server mode requested
    args = _parse_args() if len(sys.argv) > 1 else None
    if args and getattr(args, "mcp", False):
        from .mcp_server import run_mcp_server as _run_mcp
        _run_mcp()
        return 0

    if args and (getattr(args, "command", None) == "init" or getattr(args, "init", False)):
        target_dir = getattr(args, "target_dir", None) or Path.cwd()
        run_init(target_dir)
        return 0

    cfg: AppConfig | None
    if len(sys.argv) == 1 or args is None:
        cfg = _interactive_prompt()
        if cfg is None:
            return 0
    else:
        cfg = _build_config(args)

    # Observability first: Sentry -> OTel -> structlog -> global exception hooks.
    try:
        setup_observability(cfg.log_path)
    except Exception as e:
        print(f"[WARNING] Failed to setup observability: {e}. Falling back to standard logging.", file=sys.stderr)

    if cfg.mode == "login":
        _run_manual_login(cfg)
        return 0

    # ── Single-instance lock (P1) ──────────────────────────────────────────
    try:
        instance_lock = SingleInstanceLock()
    except Exception as e:
        print(f"[ERROR] Failed to acquire single instance lock: {e}", file=sys.stderr)
        return 1

    with instance_lock:
        ctx = RunContext()
        bind_run_context(run_id=ctx.run_id, mode=cfg.mode, headless=cfg.headless)
        audit = AuditLog(cfg.log_path)

        with start_span("qwen-cli.run") as span:
            if span is not None:
                span.set_attribute("mode", cfg.mode)
                span.set_attribute("run_id", ctx.run_id)
                span.set_attribute("headless", cfg.headless)

            # Install signal handlers for graceful watcher shutdown (P4)
            _install_watcher_signal_handlers()

            try:
                with browser_session(cfg) as bctx:
                    client = QwenClient(bctx, cfg)

                    if cfg.mode == "watcher":
                        _run_watcher(client, cfg, audit)
                    else:
                        # batch / single mode: same loop as before
                        for proc_file, rel_path in _iter_todo(cfg):
                            _process_file(client, proc_file, rel_path, cfg, audit, ctx)
            except AuthRequiredError as e:
                print(f"\n[AUTH ERROR] {e}\n", file=sys.stderr)
                log.error("auth_required", error=str(e))
                return 1
            except Exception as e:
                log.exception("run_failed", error_type=type(e).__name__, error=str(e))
                return exit_code_for(e)
            finally:
                # Notify systemd of graceful stop (P1)
                sd_notify_stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
