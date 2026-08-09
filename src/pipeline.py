"""Queue processing pipeline, path resolution, and audit logging.

P6 additions:
  - CircuitBreaker : tracks consecutive failures and trips when threshold exceeded.
  - RateLimiter    : enforces max requests per minute.
  - _write_sidecar : writes metadata JSON next to each output file.
"""
from __future__ import annotations

import json
import signal
import shutil
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, List, Optional, Tuple

from tenacity import RetryCallState, Retrying, retry_if_exception, stop_after_attempt, wait_exponential

try:
    from .config import AppConfig, AuthRequiredError, DEFAULT_LOG, DEFAULT_TODO, RunContext, BrowserLaunchError
    from .observability import get_logger, start_span
    from .qwen_client import QwenClient
except ImportError:
    from config import AppConfig, AuthRequiredError, DEFAULT_LOG, DEFAULT_TODO, RunContext, BrowserLaunchError
    from observability import get_logger, start_span
    from qwen_client import QwenClient

log = get_logger("pipeline")

# ─── Watcher graceful-shutdown state ─────────────────────────────────────────
_watcher_shutdown: threading.Event = threading.Event()
_WATCHER_SLEEP_CHUNK_SECS = 1


def _install_watcher_signal_handlers() -> None:
    """Register SIGINT/SIGTERM handlers that request watcher shutdown."""

    def _handle_signal(signum: int, _frame: Any) -> None:
        log.info("watcher_shutdown_requested", signal=signum)
        _watcher_shutdown.set()

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except (OSError, ValueError):
        # Windows or unsupported signal environments: graceful shutdown is best-effort.
        pass


def _watcher_sleep(interval: int) -> None:
    """Sleep in small chunks so shutdown remains responsive."""
    for _ in range(max(1, interval)):
        if _watcher_shutdown.is_set():
            return
        time.sleep(min(_WATCHER_SLEEP_CHUNK_SECS, interval))

# ─── Circuit breaker (P6) ────────────────────────────────────────────────────
class CircuitBreaker:
    """Sliding-window circuit breaker for request-level failure tracking.

    Trips when consecutive failures exceed the threshold within the configured
    window seconds. Resets on a successful request.
    """

    def __init__(self, threshold: int = 5, window_sec: int = 30) -> None:
        self._threshold = threshold
        self._window_sec = window_sec
        self._failures: deque[float] = deque()
        self._trip: bool = False

    def record_success(self) -> None:
        """Reset the breaker on a successful request."""
        self._failures.clear()
        self._trip = False

    def record_failure(self) -> None:
        """Record a failure and trip if threshold exceeded within window."""
        now = time.time()
        self._failures.append(now)
        # Prune old entries outside the window
        while self._failures and (now - self._failures[0]) > self._window_sec:
            self._failures.popleft()
        if len(self._failures) >= self._threshold:
            self._trip = True

    @property
    def is_tripped(self) -> bool:
        return self._trip


# ─── Rate limiter (P6) ───────────────────────────────────────────────────────
class RateLimiter:
    """Simple token-bucket rate limiter for request throttling.

    Tracks the last N request timestamps and enforces a minimum interval.
    """

    def __init__(self, max_per_minute: int = 60) -> None:
        self._max_per_minute = max_per_minute
        self._timestamps: deque[float] = deque()

    def acquire(self) -> None:
        """Wait until a request slot is available."""
        now = time.time()
        window_start = now - 60.0  # 1-minute sliding window
        while True:
            # Prune old timestamps
            while self._timestamps and self._timestamps[0] < window_start:
                self._timestamps.popleft()
            if len(self._timestamps) < self._max_per_minute:
                break
            # Calculate how long to wait
            oldest = self._timestamps[0]
            wait_sec = 60.0 - (now - oldest) + 0.1  # +0.1s buffer
            if wait_sec > 0:
                time.sleep(wait_sec)
                now = time.time()
        self._timestamps.append(time.time())


# ─── Retry policy ────────────────────────────────────────────────────────────
# 3 attempts, exponential backoff (2s, 4s, ... capped at 30s), re-raise the
# original exception. AuthRequiredError is permanent: never retried.
MAX_ATTEMPTS = 3


def _retry_policy(client: QwenClient, audit: AuditLog, ctx: RunContext, rel_path: Path) -> Retrying:
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

    def __init__(self, log_dir: Optional[Path] = None) -> None:
        target_dir = log_dir or DEFAULT_LOG
        target_dir.mkdir(parents=True, exist_ok=True)
        self._audit = target_dir / "audit_history.jsonl"
        self._errors = target_dir / "errors.log"
        self._errors_jsonl = target_dir / "errors.jsonl"

    def log_step(self, ctx: RunContext, step: str, src: str, status: str, details: Optional[dict[str, Any]] = None) -> None:
        """Logs granular step-by-step event execution for end-to-end traceability."""
        rec = {
            "run_id": ctx.run_id,
            "timestamp": datetime.now().isoformat(),
            "event": "step_execution",
            "step": step,
            "source_file": src,
            "status": status,
        }
        if details:
            rec["details"] = details
        with self._audit.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def log(self, status: str, ctx: RunContext, src: str, dst: str, dur: float, in_c: int, out_c: int, err: str = "") -> None:
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


def _write_output(path: Path, content: str, ctx: RunContext, src: str, dur: float, in_c: int, out_c: int) -> None:
    """Writes processed output to disk with metadata traceability header."""
    header = (
        "<!--\n"
        "--- METADATA TRACEABILITY ---\n"
        f"Run ID           : {ctx.run_id}\n"
        f"Source File      : {src}\n"
        f"Processed At     : {datetime.now().isoformat()}\n"
        f"Duration         : {dur:.2f}s\n"
        f"Input Characters : {in_c}\n"
        f"Output Characters: {out_c}\n"
        "-----------------------------\n"
        "-->\n\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + content, encoding="utf-8")

    # P6: Write sidecar metadata JSON next to the output file
    sidecar_path = path.with_suffix(".meta.json")
    try:
        meta = {
            "run_id": ctx.run_id,
            "source_file": src,
            "processed_at": datetime.now().isoformat(),
            "duration_sec": round(dur, 2),
            "input_chars": in_c,
            "output_chars": out_c,
        }
        sidecar_path.write_text(json.dumps(meta, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass  # Non-fatal

    print(f"  📋 [EVENT_OUTPUT_COPIED] Output successfully copied to file {path.name}")


def load_role_prompt(file_path: Path, custom_prompt_path: Optional[Path] = None, rel_path: Optional[Path] = None) -> str:
    """Dynamically loads custom PROMPT.md from file's parent role directory in input/."""
    if custom_prompt_path and custom_prompt_path.exists() and custom_prompt_path.is_file():
        content = custom_prompt_path.read_text(encoding="utf-8").strip()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()
        return content

    search_dirs: List[Path] = []

    if rel_path and rel_path.parts and rel_path.parts[0].startswith("role-"):
        role_dir_rel = DEFAULT_TODO / rel_path.parts[0]
        search_dirs.append(role_dir_rel)
        search_dirs.append(role_dir_rel.resolve())

    abs_path = file_path.resolve()
    curr_abs = abs_path.parent if abs_path.is_file() else abs_path
    search_dirs.append(curr_abs)
    search_dirs.extend(curr_abs.parents)

    curr_rel = file_path.parent if file_path.is_file() else file_path
    if curr_rel not in search_dirs:
        search_dirs.append(curr_rel)
        search_dirs.extend(curr_rel.parents)

    for path_obj in [abs_path, file_path]:
        for part in path_obj.parts:
            if part.startswith("role-"):
                role_dir_abs = DEFAULT_TODO.resolve() / part
                if role_dir_abs not in search_dirs:
                    search_dirs.append(role_dir_abs)
                role_dir_rel = DEFAULT_TODO / part
                if role_dir_rel not in search_dirs:
                    search_dirs.append(role_dir_rel)

    for p in search_dirs:
        prompt_file = p / "PROMPT.md"
        if prompt_file.exists() and prompt_file.is_file():
            content = prompt_file.read_text(encoding="utf-8").strip()
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            if content:
                log.info("Loaded role prompt from %s (%d chars)", prompt_file, len(content))
                return content
    return ""


def resolve_role_paths(rel_path: Path, cfg: AppConfig) -> Tuple[Path, Path, Path, Path]:
    """
    Resolves role-based paths for output, done, failed, and processing.
    If rel_path starts with a role folder (e.g. role-architect), stores done/.processing/failed inside that role folder!
    Returns (out_path, done_path, fail_path, proc_file).
    """
    parts = rel_path.parts
    if parts and parts[0].startswith("role-"):
        role_folder = parts[0]
        sub_parts = parts[1:]
        if sub_parts and sub_parts[0] == "todo":
            sub_parts = sub_parts[1:]
        sub_path = Path(*sub_parts) if sub_parts else Path(rel_path.name)

        out_path = cfg.output_path / role_folder / sub_path
        done_path = DEFAULT_TODO / role_folder / "done" / sub_path
        fail_path = DEFAULT_TODO / role_folder / "failed" / sub_path
        proc_file = DEFAULT_TODO / role_folder / ".processing" / sub_path
    else:
        sub_parts = parts
        if sub_parts and sub_parts[0] == "todo":
            sub_parts = sub_parts[1:]
        sub_path = Path(*sub_parts) if sub_parts else Path(rel_path.name)

        out_path = cfg.output_path / sub_path if not (cfg.mode == "single" and cfg.output_path.suffix) else cfg.output_path
        done_path = cfg.done_path / sub_path
        fail_path = cfg.failed_path / sub_path
        proc_file = cfg.proc_path / sub_path

    return out_path, done_path, fail_path, proc_file


def _list_input_files(src: Path) -> List[Tuple[Path, Path]]:
    """List processable files in input directory as (absolute_path, relative_path) tuples."""
    skip_dirs = {"done", "failed", ".processing", "proc"}
    files: List[Tuple[Path, Path]] = []
    if not src.exists() or not src.is_dir():
        return files
    for f in sorted(f for f in src.rglob("*") if f.is_file()):
        if f.name.startswith(".") or f.name.upper() == "PROMPT.MD":
            continue
        rel_parts = f.relative_to(src).parts
        if any(p in skip_dirs or p.startswith(".") for p in rel_parts[:-1]):
            continue
        files.append((f, f.relative_to(src)))
    return files


def _iter_todo(cfg: AppConfig) -> Iterator[Tuple[Path, Path]]:
    """Yield (proc_file, relative_path) tuples for processing queue."""
    src = cfg.input_path if cfg.input_path.is_dir() else DEFAULT_TODO
    src.mkdir(parents=True, exist_ok=True)
    cfg.proc_path.mkdir(parents=True, exist_ok=True)

    skip_dirs = {"done", "failed", ".processing", "proc"}

    def _should_process(f: Path, base_src: Path) -> bool:
        if not f.is_file():
            return False
        if f.name.startswith(".") or f.name.upper() == "PROMPT.MD":
            return False
        rel_parts = f.resolve().relative_to(base_src.resolve()).parts
        if any(p in skip_dirs or p.startswith(".") for p in rel_parts[:-1]):
            return False
        return True

    # P6: retry-failed mode — process files from failed/ on next run
    if cfg.retry_failed:
        src = cfg.failed_path
        if not src.exists() or not src.is_dir():
            log.warning("retry-failed mode: failed/ directory not found")
            return
        for f in sorted(f for f in src.rglob("*") if _should_process(f, src)):
            rel_path = f.resolve().relative_to(src.resolve())
            _, _, _, proc_dest = resolve_role_paths(rel_path, cfg)
            proc_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(proc_dest))
            yield proc_dest, rel_path
        return

    if cfg.mode == "single":
        if not cfg.input_path.exists():
            raise FileNotFoundError(cfg.input_path)
        try:
            rel_path = cfg.input_path.resolve().relative_to(DEFAULT_TODO.resolve())
        except ValueError:
            abs_p = cfg.input_path.resolve()
            parts = abs_p.parts
            role_idx = next((i for i, part in enumerate(parts) if part.startswith("role-")), None)
            if role_idx is not None:
                rel_path = Path(*parts[role_idx:])
            else:
                rel_path = Path(cfg.input_path.name)
        _, _, _, proc_file = resolve_role_paths(rel_path, cfg)
        proc_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cfg.input_path, proc_file)
        yield proc_file, rel_path
        return

    if cfg.mode == "batch":
        for f in sorted(f for f in src.rglob("*") if _should_process(f, src)):
            rel_path = f.resolve().relative_to(src.resolve())
            _, _, _, proc_dest = resolve_role_paths(rel_path, cfg)
            proc_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(proc_dest))
            yield proc_dest, rel_path
        return

    log.info("watching %s every %ds", src, cfg.interval)
    _install_watcher_signal_handlers()
    while True:
        for f in sorted(f for f in src.rglob("*") if _should_process(f, src)):
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


def _process_file(client: QwenClient, proc_file: Path, rel_path: Path,
                  cfg: AppConfig, audit: AuditLog, ctx: RunContext) -> None:
    """Processes single file through Qwen web client with tenacity retry and quarantine handling."""
    out_path, done_path, fail_path, _ = resolve_role_paths(rel_path, cfg)

    prompt = proc_file.read_text(encoding="utf-8").strip()
    print(f"• {rel_path} ({len(prompt):,} chars)")
    t0 = time.time()
    audit.log_step(ctx, "START_PROCESSING", str(rel_path), "STARTED", {"input_chars": len(prompt)})

    # P6: Initialize circuit breaker and rate limiter for this request
    cb = CircuitBreaker(
        threshold=cfg.circuit_breaker_threshold,
        window_sec=cfg.circuit_breaker_window,
    )
    rl = RateLimiter(max_per_minute=cfg.rate_limit_per_minute)

    def _attempt() -> str:
        # Acquire rate limiter slot
        rl.acquire()

        text = client.send_file(proc_file, cfg.timeout, custom_prompt_path=cfg.prompt_file, rel_path=rel_path)
        dur = time.time() - t0

        # P6: Record success on circuit breaker
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
        print(f"  -> {out_path} ({dur:.1f}s)")
        return text

    try:
        with start_span("process_file") as span:
            if span is not None:
                span.set_attribute("source_file", str(rel_path))
                span.set_attribute("input_chars", len(prompt))
            for attempt in _retry_policy(client, audit, ctx, rel_path):
                with attempt:
                    return _attempt()
    except AuthRequiredError:
        raise
    except Exception as e:
        dur = time.time() - t0

        # P6: Record failure on circuit breaker
        cb.record_failure()

        err_msg = f"{type(e).__name__}: {e}"
        audit.log("FAILED", ctx, str(rel_path), str(out_path), dur, len(prompt), 0, err_msg)
        audit.log_step(ctx, "QUARANTINED", str(rel_path), "FAILED", {"error": err_msg})

        client.reset_page()
        if out_path.resolve() != fail_path.resolve():
            fail_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(proc_file), str(fail_path))
        else:
            try:
                proc_file.unlink()
            except Exception:
                pass
        print(f"  x QUARANTINED to {fail_path}: {e}")
