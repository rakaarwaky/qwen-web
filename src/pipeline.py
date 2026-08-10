"""Queue processing pipeline, path resolution, and audit logging.

Refactored with modular, low-complexity functions, circuit breaker, rate limiter,
and structured audit logging.
"""

from __future__ import annotations

import json
import shutil
import signal
import threading
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from .observability import get_logger, start_span
from .qwen_client import QwenClient
from .saver import write_output as _write_output
from .types import (
    DEFAULT_LOG,
    DEFAULT_TODO,
    AppConfig,
    AuthRequiredError,
    CircuitBreaker,
    CircuitBreakerOpenError,
    RateLimiter,
    RunContext,
)

log = get_logger("pipeline")

# ─── Watcher graceful-shutdown state ─────────────────────────────────────────
_watcher_shutdown: threading.Event = threading.Event()
_WATCHER_SLEEP_CHUNK_SECS = 1
MAX_ATTEMPTS = 3
SKIP_DIRS = {"done", "failed", ".processing", "proc"}


def request_watcher_shutdown() -> None:
    """Signal watcher loop to shutdown gracefully."""
    _watcher_shutdown.set()


def is_watcher_shutdown_set() -> bool:
    """Return True if watcher shutdown has been requested."""
    return _watcher_shutdown.is_set()


def _install_watcher_signal_handlers() -> None:
    """Register SIGINT/SIGTERM handlers that request watcher shutdown."""

    def _handle_signal(signum: int, _frame: Any) -> None:
        log.info("watcher_shutdown_requested", signal=signum)
        _watcher_shutdown.set()

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except (OSError, ValueError):
        pass


def _watcher_sleep(interval: int) -> None:
    """Sleep in small chunks so shutdown remains responsive."""
    for _ in range(max(1, interval)):
        if _watcher_shutdown.is_set():
            return
        time.sleep(min(_WATCHER_SLEEP_CHUNK_SECS, interval))


def _retry_policy(client: QwenClient, audit: AuditLog, ctx: RunContext, rel_path: Path) -> Retrying:
    """Construct tenacity retry policy with exponential backoff and audit logging."""

    def _before_sleep(retry_state: RetryCallState) -> None:
        attempt = retry_state.attempt_number
        exc = retry_state.outcome.exception() if retry_state.outcome else RuntimeError("unknown")
        wait_sec = retry_state.next_action.sleep if retry_state.next_action else 2
        client.reset_page()
        audit.log_step(
            ctx,
            f"ATTEMPT_{attempt}_FAILED",
            str(rel_path),
            "FAILED",
            {"error": str(exc), "error_type": type(exc).__name__, "wait_sec": wait_sec},
        )
        log.warning(
            "attempt_failed_retrying",
            file=str(rel_path),
            attempt=attempt,
            next_wait_sec=wait_sec,
            error=str(exc),
        )

    return Retrying(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(lambda e: not isinstance(e, AuthRequiredError)),
        before_sleep=_before_sleep,
        reraise=True,
    )


class AuditLog:
    """Logs structured JSONL audit history and error traces with step-level context."""

    def __init__(self, log_dir: Path | None = None) -> None:
        """Initialize audit log files in the target directory."""
        target_dir = log_dir or DEFAULT_LOG
        target_dir.mkdir(parents=True, exist_ok=True)
        self._audit = target_dir / "audit_history.jsonl"
        self._errors = target_dir / "errors.log"
        self._errors_jsonl = target_dir / "errors.jsonl"

    def log_step(
        self,
        ctx: RunContext,
        step: str,
        src: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log granular step-by-step event execution for end-to-end traceability."""
        rec: dict[str, Any] = {
            "run_id": ctx.run_id,
            "timestamp": datetime.now().isoformat(),
            "event": "step_execution",
            "step": step,
            "source_file": src,
            "status": status,
        }
        if details is not None:
            rec["details"] = details
        with self._audit.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def log(
        self,
        status: str,
        ctx: RunContext,
        src: str,
        dst: str,
        dur: float,
        in_c: int,
        out_c: int,
        err: str = "",
    ) -> None:
        """Log a completed file processing result with duration and character counts."""
        rec = {
            "run_id": ctx.run_id,
            "timestamp": datetime.now().isoformat(),
            "source_file": src,
            "output_file": dst,
            "status": status,
            "duration_sec": dur,
            "input_chars": in_c,
            "output_chars": out_c,
        }
        if err:
            rec["error"] = err
        with self._audit.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if err:
            err_entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [run_id={ctx.run_id}] {src}: {err}\n\n"
            with self._errors.open("a", encoding="utf-8") as f:
                f.write(err_entry)

            err_json_rec = {
                "run_id": ctx.run_id,
                "timestamp": datetime.now().isoformat(),
                "source_file": src,
                "output_file": dst,
                "error": err,
                "duration_sec": dur,
                "input_chars": in_c,
            }
            with self._errors_jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(err_json_rec, ensure_ascii=False) + "\n")


def _extract_prompt_text(content: str) -> str:
    """Strip YAML frontmatter header if present."""
    stripped = content.strip()
    if stripped.startswith("---"):
        parts = stripped.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return stripped


def _strip_input_from_output(text: str, full_prompt: str) -> str:
    """Strip leaked input content from AI response.

    When DOM scraping returns user input mixed with AI response,
    this strips the prompt prefix to return only the AI's output.
    """
    if not text or not full_prompt:
        return text

    prompt_stripped = full_prompt.strip()
    text_stripped = text.strip()

    if text_stripped.startswith(prompt_stripped):
        candidate = text_stripped[len(prompt_stripped):].lstrip("\n")
        if len(candidate.strip()) > 20:
            log.info("Stripped %d chars of leaked input from response", len(prompt_stripped))
            return candidate

    lines = text_stripped.splitlines()
    prompt_lines = set(prompt_stripped.splitlines())
    if prompt_lines and len(prompt_lines) > 5:
        matching = sum(1 for l in lines if l.strip() in prompt_lines)
        if matching >= len(prompt_lines) * 0.8 and matching > 3:
            filtered = [l for l in lines if l.strip() not in prompt_lines]
            result = "\n".join(filtered).strip()
            if len(result) > 20:
                log.info("Filtered %d matching prompt lines from response", matching)
                return result

    return text


def _get_role_search_directories(file_path: Path, rel_path: Path | None) -> list[Path]:
    """Collect priority list of directories to search for PROMPT.md."""
    search_dirs: list[Path] = []

    if rel_path and rel_path.parts and rel_path.parts[0].startswith("role-"):
        role_dir_rel = DEFAULT_TODO / rel_path.parts[0]
        search_dirs.extend([role_dir_rel, role_dir_rel.resolve()])

    abs_path = file_path.resolve()
    curr_abs = abs_path.parent if abs_path.is_file() else abs_path
    search_dirs.append(curr_abs)
    search_dirs.extend(curr_abs.parents)

    curr_rel = file_path.parent if file_path.is_file() else file_path
    if curr_rel not in search_dirs:
        search_dirs.append(curr_rel)
        search_dirs.extend(curr_rel.parents)

    for path_obj in (abs_path, file_path):
        for part in path_obj.parts:
            if part.startswith("role-"):
                search_dirs.extend([DEFAULT_TODO.resolve() / part, DEFAULT_TODO / part])

    return search_dirs


def load_role_prompt(
    file_path: Path,
    custom_prompt_path: Path | None = None,
    rel_path: Path | None = None,
) -> str:
    """Dynamically loads custom PROMPT.md from file's parent role directory in input/."""
    if custom_prompt_path and custom_prompt_path.exists() and custom_prompt_path.is_file():
        return _extract_prompt_text(custom_prompt_path.read_text(encoding="utf-8"))

    for p in _get_role_search_directories(file_path, rel_path):
        prompt_file = p / "PROMPT.md"
        if prompt_file.exists() and prompt_file.is_file():
            content = _extract_prompt_text(prompt_file.read_text(encoding="utf-8"))
            if content:
                log.info("Loaded role prompt from %s (%d chars)", prompt_file, len(content))
                return content
    return ""


def resolve_role_paths(rel_path: Path, cfg: AppConfig) -> tuple[Path, Path, Path, Path]:
    """Resolve role-based paths for output, done, failed, and processing.

    Returns (out_path, done_path, fail_path, proc_file).
    """
    parts = rel_path.parts
    is_single_file_input = cfg.mode == "single" or bool(cfg.input_path.suffix) or cfg.input_path.is_file()
    base = DEFAULT_TODO if is_single_file_input else cfg.input_path

    # Check if role-* exists in parts (either at start or anywhere in the path)
    role_idx = next((i for i, p in enumerate(parts) if p.startswith("role-")), None)
    if role_idx is not None:
        role_folder = parts[role_idx]
        sub_parts = parts[role_idx + 1:]
        if sub_parts and sub_parts[0] in ("todo", "done", "failed", ".processing", "proc"):
            sub_parts = sub_parts[1:]
        sub_path = Path(*sub_parts) if sub_parts else Path(rel_path.name)

        out_path = (
            cfg.output_path / sub_path.name
            if not (cfg.mode == "single" and cfg.output_path.suffix)
            else cfg.output_path
        )
        done_path = base / role_folder / "done" / sub_path
        fail_path = base / role_folder / "failed" / sub_path
        proc_file = cfg.proc_path / role_folder / sub_path
    else:
        sub_parts = parts
        if sub_parts and sub_parts[0] in ("todo", "done", "failed", ".processing", "proc"):
            sub_parts = sub_parts[1:]
        sub_path = Path(*sub_parts) if sub_parts else Path(rel_path.name)

        out_path = (
            cfg.output_path / sub_path.name
            if not (cfg.mode == "single" and cfg.output_path.suffix)
            else cfg.output_path
        )
        done_path = cfg.done_path / sub_path
        fail_path = cfg.failed_path / sub_path
        proc_file = cfg.proc_path / sub_path

    return out_path, done_path, fail_path, proc_file



def _should_process_file(f: Path, base_src: Path) -> bool:
    """Check if file qualifies for queue processing."""
    if not f.is_file() or f.name.startswith(".") or f.name.upper() == "PROMPT.MD":
        return False
    try:
        rel_parts = f.resolve().relative_to(base_src.resolve()).parts
    except ValueError:
        return False

    if len(rel_parts) < 2 or not rel_parts[0].startswith("role-"):
        return False
    return not any(p in SKIP_DIRS or p.startswith(".") for p in rel_parts[:-1])


def _list_input_files(base_path: Path) -> list[tuple[Path, Path]]:
    """List input files from base_path, excluding PROMPT.md and internal folders."""
    if not base_path.is_dir():
        return []
    return [
        (f, f.resolve().relative_to(base_path.resolve()))
        for f in sorted(f for f in base_path.rglob("*") if _should_process_file(f, base_path))
    ]


def _iter_todo_retry_failed(cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
    """Yield files for retry-failed mode."""
    src = cfg.failed_path
    if not src.exists() or not src.is_dir():
        log.warning("retry-failed mode: failed/ directory not found")
        return
    for f in sorted(f for f in src.rglob("*") if _should_process_file(f, src)):
        rel_path = f.resolve().relative_to(src.resolve())
        _, _, _, proc_dest = resolve_role_paths(rel_path, cfg)
        proc_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(proc_dest))
        yield proc_dest, rel_path


def _iter_todo_single(cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
    """Yield file for single mode."""
    if not cfg.input_path.exists():
        raise FileNotFoundError(cfg.input_path)
    try:
        rel_path = cfg.input_path.resolve().relative_to(DEFAULT_TODO.resolve())
    except ValueError:
        abs_p = cfg.input_path.resolve()
        parts = abs_p.parts
        role_idx = next((i for i, part in enumerate(parts) if part.startswith("role-")), None)
        rel_path = Path(*parts[role_idx:]) if role_idx is not None else Path(cfg.input_path.name)

    _, _, _, proc_file = resolve_role_paths(rel_path, cfg)
    proc_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(cfg.input_path), str(proc_file))
    yield proc_file, rel_path


def _iter_todo_batch(src: Path, cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
    """Yield files for batch mode."""
    for f in sorted(f for f in src.rglob("*") if _should_process_file(f, src)):
        rel_path = f.resolve().relative_to(src.resolve())
        _, _, _, proc_dest = resolve_role_paths(rel_path, cfg)
        proc_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(proc_dest))
        yield proc_dest, rel_path


def _iter_todo_watcher(src: Path, cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
    """Yield files continuously in watcher mode."""
    log.info("watching %s every %ds", src, cfg.interval)
    _install_watcher_signal_handlers()
    while True:
        for f in sorted(f for f in src.rglob("*") if _should_process_file(f, src)):
            if _watcher_shutdown.is_set():
                log.info("watcher_exiting_on_shutdown")
                return
            rel_path = f.resolve().relative_to(src.resolve())
            _, _, _, proc_dest = resolve_role_paths(rel_path, cfg)
            proc_dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(f), str(proc_dest))
                yield proc_dest, rel_path
            except OSError as e:
                log.debug("skipping %s: %s", f, e)
        if _watcher_shutdown.is_set():
            log.info("watcher_exiting_on_shutdown")
            return
        _watcher_sleep(cfg.interval)


def _iter_todo(cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
    """Yield (proc_file, relative_path) tuples for processing queue."""
    src = cfg.input_path if cfg.input_path.is_dir() else DEFAULT_TODO
    src.mkdir(parents=True, exist_ok=True)
    cfg.proc_path.mkdir(parents=True, exist_ok=True)

    if cfg.retry_failed:
        yield from _iter_todo_retry_failed(cfg)
        return

    if cfg.mode == "single":
        yield from _iter_todo_single(cfg)
        return

    if cfg.mode == "batch":
        yield from _iter_todo_batch(src, cfg)
        return

    yield from _iter_todo_watcher(src, cfg)


def _execute_single_attempt(
    client: QwenClient,
    proc_file: Path,
    rel_path: Path,
    cfg: AppConfig,
    audit: AuditLog,
    ctx: RunContext,
    cb: CircuitBreaker,
    rl: RateLimiter,
    t0: float,
    prompt: str,
    out_path: Path,
    done_path: Path,
) -> str:
    """Execute single attempt to process file through QwenClient."""
    rl.acquire()

    role_prompt = load_role_prompt(proc_file, cfg.prompt_file, rel_path)
    full_prompt = f"{role_prompt}\n\n{prompt}" if role_prompt else prompt

    text = client.send_file(proc_file, cfg.timeout, custom_prompt_path=cfg.prompt_file, rel_path=rel_path)
    dur = time.time() - t0

    text = _strip_input_from_output(text, full_prompt)

    cb.record_success()
    _write_output(out_path, text, ctx, str(rel_path), dur, len(prompt), len(text))
    audit.log("SUCCESS", ctx, str(rel_path), str(out_path), dur, len(prompt), len(text))
    audit.log_step(ctx, "PROCESS_SUCCESS", str(rel_path), "SUCCESS", {"duration_sec": dur, "output_chars": len(text)})

    if out_path.resolve() == done_path.resolve():
        try:
            proc_file.unlink()
        except Exception:
            pass
    else:
        done_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(proc_file), str(done_path))

    _cleanup_empty_dirs(proc_file.parent, cfg.proc_path)
    log.info("processed_file_success", out_path=str(out_path), duration_sec=round(dur, 1))
    return text


def _cleanup_empty_dirs(dir_path: Path, root_limit: Path) -> None:
    """Remove empty parent directories up to root_limit."""
    try:
        curr = dir_path
        root_res = root_limit.resolve()
        while curr.exists() and curr.resolve() != root_res and root_res in curr.resolve().parents:
            if not any(curr.iterdir()):
                curr.rmdir()
                curr = curr.parent
            else:
                break
    except Exception:
        pass


def _handle_processing_failure(
    client: QwenClient,
    proc_file: Path,
    rel_path: Path,
    audit: AuditLog,
    ctx: RunContext,
    cb: CircuitBreaker,
    t0: float,
    prompt: str,
    out_path: Path,
    fail_path: Path,
    exc: Exception,
    cfg: AppConfig | None = None,
) -> None:
    """Record failure metrics, update circuit breaker, and quarantine file."""
    dur = time.time() - t0
    cb.record_failure()

    err_msg = f"{type(exc).__name__}: {exc}"
    audit.log("FAILED", ctx, str(rel_path), str(out_path), dur, len(prompt), 0, err_msg)
    audit.log_step(ctx, "QUARANTINED", str(rel_path), "FAILED", {"error": err_msg})

    client.reset_page()
    if out_path.resolve() != fail_path.resolve() and proc_file.exists():
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(proc_file), str(fail_path))
    else:
        try:
            proc_file.unlink()
        except Exception:
            pass

    if cfg:
        _cleanup_empty_dirs(proc_file.parent, cfg.proc_path)
    log.error("file_quarantined", fail_path=str(fail_path), error=str(exc))


def _process_file(
    client: QwenClient,
    proc_file: Path,
    rel_path: Path,
    cfg: AppConfig,
    audit: AuditLog,
    ctx: RunContext,
    cb: CircuitBreaker | None = None,
    rl: RateLimiter | None = None,
) -> None:
    """Process single file through Qwen web client with tenacity retry and quarantine handling."""
    out_path, done_path, fail_path, _ = resolve_role_paths(rel_path, cfg)

    active_cb = cb or CircuitBreaker(
        threshold=cfg.circuit_breaker_threshold,
        window_sec=cfg.circuit_breaker_window,
    )
    active_rl = rl or RateLimiter(max_per_minute=cfg.rate_limit_per_minute)

    if active_cb.is_tripped:
        raise CircuitBreakerOpenError(
            f"Circuit breaker tripped ({cfg.circuit_breaker_threshold} consecutive failures in "
            f"{cfg.circuit_breaker_window}s). Aborting {rel_path}"
        )

    prompt = proc_file.read_text(encoding="utf-8").strip()
    log.info("processing_file", file=str(rel_path), chars=len(prompt))
    t0 = time.time()
    audit.log_step(ctx, "START_PROCESSING", str(rel_path), "STARTED", {"input_chars": len(prompt)})

    try:
        with start_span("process_file") as span:
            if span is not None:
                span.set_attribute("source_file", str(rel_path))
                span.set_attribute("input_chars", len(prompt))

            for attempt in _retry_policy(client, audit, ctx, rel_path):
                with attempt:
                    _execute_single_attempt(
                        client, proc_file, rel_path, cfg, audit, ctx,
                        active_cb, active_rl, t0, prompt, out_path, done_path,
                    )
                    break
    except AuthRequiredError:
        raise
    except Exception as exc:
        _handle_processing_failure(
            client, proc_file, rel_path, audit, ctx, active_cb, t0, prompt, out_path, fail_path, exc
        )
