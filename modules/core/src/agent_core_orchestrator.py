"""Agent: core feature orchestrator (AES405).

Orchestration-only layer. Coordinates capabilities through protocol ABCs —
zero direct I/O, zero business logic, zero domain computation. Implements
ICoreAggregate, consumed by the CLI/MCP surfaces.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_config_factory import build_app_config
from modules.core.src.utility_core_error_mapping import to_error_response
from modules.core.src.utility_core_file_mover import move_file, move_to_processing
from modules.core.src.utility_core_io_writer import ensure_dir
from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.contract_core_protocol import (
    IAuditProtocol,
    IBrowserProtocol,
    IInjectionProtocol,
    IObservabilityProtocol,
    ISaverProtocol,
    ISendProtocol,
    IStreamProtocol,
    IUploadProtocol,
)
from modules.shared.src.contract_workspace_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import (
    _WATCHER_SLEEP_CHUNK_SECS,
    CHAT_URL,
    DEFAULT_OUTPUT,
    DEFAULT_TODO,
)
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, LifecycleEmitter, RateLimiter
from modules.shared.src.taxonomy_core_vo import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_DOCUMENT_PARSED,
    EVENT_OUTPUT_COPIED,
    FilePath,
    HeadlessFlag,
    MessageCount,
    OutputChars,
    PromptText,
    ResponseText,
    RunContext,
    TimeoutSec,
)
from modules.shared.src.taxonomy_domain_error import (
    AuthRequiredError,
    CircuitBreakerOpenError,
    QwenCliError,
)
from modules.shared.src.utility_core_path import (
    cleanup_empty_dirs,
    resolve_role_paths,
    should_process_file,
)
from modules.shared.src.utility_core_prompt import load_role_prompt, strip_input_from_output

_watcher_shutdown: threading.Event = threading.Event()


def request_watcher_shutdown() -> None:
    """Signal watcher loop to shutdown gracefully."""
    _watcher_shutdown.set()


def is_watcher_shutdown_set() -> bool:
    """Return True if watcher shutdown has been requested."""
    return _watcher_shutdown.is_set()


def _watcher_sleep(interval: int) -> None:
    """Sleep in small chunks so shutdown remains responsive (module-level shim).

    Delegates to the same logic used by CoreOrchestrator._watcher_sleep.
    Kept for backward compatibility with callers that import this function
    directly from the module.
    """
    for _ in range(max(1, interval)):
        if _watcher_shutdown.is_set():
            return
        time.sleep(min(_WATCHER_SLEEP_CHUNK_SECS, interval))


class CoreOrchestrator(ICoreAggregate):
    """Coordinates capabilities to process prompt files through Qwen Web."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        uploader: IUploadProtocol,
        saver: ISaverProtocol,
        audit: IAuditProtocol,
        observability: IObservabilityProtocol,
        workspace: IWorkspaceProtocol,
        circuit_breaker: CircuitBreaker | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        """Inject capability dependencies via protocol ABCs."""
        self._browser = browser
        self._injector = injector
        self._sender = sender
        self._streamer = streamer
        self._uploader = uploader
        self._saver = saver
        self._audit = audit
        self._observability = observability
        self._workspace = workspace
        self._cb = circuit_breaker or CircuitBreaker()
        self._rl = rate_limiter or RateLimiter()

    # ─── ICoreAggregate implementation ──────────────────────────
    def process_single_file(
        self,
        input_file: Path | str,
        output_file: Path | str | None = None,
        headless: bool = True,
    ) -> ResponseText:
        """Process a single prompt file end-to-end."""
        in_p = Path(input_file).resolve()
        if not in_p.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        out_p = Path(output_file).resolve() if output_file else DEFAULT_OUTPUT / in_p.name
        cfg = build_app_config(
            mode="single",
            input_path=in_p,
            output_path=out_p,
            headless=headless,
        )

        ctx = RunContext()
        self._audit.log_step(ctx, "START_PROCESSING", FilePath(str(in_p.name)), "STARTED", {"input_chars": 0})

        proc_file = cfg.proc_path / in_p.name
        ensure_dir(proc_file)
        shutil.copy2(in_p, proc_file)

        def _fn() -> ResponseText:
            with self._browser.browser_session(cfg):
                self._process_file(proc_file, Path(in_p.name), cfg, ctx)
            return ResponseText(f"Successfully processed {in_p.name} -> {out_p}")

        return self._execute(_fn)

    def process_batch(
        self,
        input_dir: Path | str | None = None,
        output_dir: Path | str | None = None,
        headless: bool = True,
    ) -> ResponseText:
        """Process all prompt files inside an input directory."""
        in_p = Path(input_dir).resolve() if input_dir else DEFAULT_TODO
        out_p = Path(output_dir).resolve() if output_dir else DEFAULT_OUTPUT

        cfg = build_app_config(
            mode="batch",
            input_path=in_p,
            output_path=out_p,
            headless=headless,
        )

        ctx = RunContext()
        processed = 0
        failed = 0

        def _fn() -> ResponseText:
            nonlocal processed, failed
            with self._browser.browser_session(cfg):
                for proc_file, rel_path in self._iter_todo(cfg):
                    try:
                        self._process_file(proc_file, rel_path, cfg, ctx)
                        processed += 1
                    except Exception as e:  # per-file isolation: a failure must not abort the batch
                        failed += 1
                        self._observability.get_logger().error("batch_file_failed", file=str(rel_path), error=str(e))
            return ResponseText(f"Batch processing complete. Successfully processed: {processed}, Failed: {failed}")

        return self._execute(_fn)

    def process_watcher(self, interval_sec: int = 3, headless: bool = True) -> ResponseText:
        """Run the continuous folder watcher."""
        cfg = build_app_config(
            mode="watcher",
            input_path=DEFAULT_TODO,
            output_path=DEFAULT_OUTPUT,
            interval=interval_sec,
            headless=headless,
        )

        ctx = RunContext()

        def _fn() -> ResponseText:
            with self._browser.browser_session(cfg):
                for proc_file, rel_path in self._iter_todo(cfg):
                    self._process_file(proc_file, rel_path, cfg, ctx)
                    _watcher_sleep(cfg.interval)
            return ResponseText("Watcher loop completed.")

        return self._execute(_fn)

    def process_mode(self, cfg: AppConfig) -> ResponseText:
        """Dispatch processing based on AppConfig.mode (watcher/single/batch)."""
        if cfg.mode == "watcher":
            return self.process_watcher(interval_sec=cfg.interval, headless=cfg.headless)

        if cfg.mode == "single":
            return self.process_single_file(
                cfg.input_path,
                cfg.output_path,
                cfg.headless,
            )

        return self.process_batch(
            cfg.input_path,
            cfg.output_path,
            cfg.headless,
        )

    def send_prompt(self, prompt: str, timeout_sec: int = 120, headless: bool = True) -> ResponseText:
        """Send a direct text prompt and return the AI response."""
        fd, tmp_path = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(prompt)
        except (OSError, UnicodeError):
            with contextlib.suppress(OSError):
                os.close(fd)
            raise

        def _fn() -> ResponseText:
            cfg = build_app_config(
                mode="single",
                input_path=Path(tmp_path),
                output_path=DEFAULT_OUTPUT,
                headless=headless,
            )
            with self._browser.browser_session(cfg):
                return ResponseText(self._send_file(Path(tmp_path), timeout_sec, None, None, cfg))

        def _cleanup() -> None:
            p = Path(tmp_path)
            if p.exists():
                p.unlink()

        return self._execute_with_cleanup(_fn, _cleanup)

    def setup_session(self) -> ResponseText:
        """Launch a visible browser for manual login / session setup."""
        cfg = build_app_config(
            mode="login",
            input_path=DEFAULT_TODO,
            output_path=DEFAULT_OUTPUT,
            headless=False,
        )
        with self._browser.browser_session(cfg) as bctx:
            page = bctx.pages[0] if bctx.pages else bctx.new_page()
            page.goto(CHAT_URL, wait_until="domcontentloaded")
        return ResponseText(f"Browser session saved to '{cfg.session_path}'. You can now run tasks in headless mode.")

    def get_audit_log(self, limit: int = 20) -> ResponseText:
        """Return recent audit log entries as JSON text (delegated to audit capability)."""
        return self._audit.get_audit_log(MessageCount(limit))

    def init_workspace(self, target_dir: Path | FilePath = FilePath(".")) -> None:
        """Initialize the workspace (delegated to IWorkspaceProtocol)."""
        self._workspace.init_workspace(FilePath(str(Path(target_dir))))

    def send_file(
        self,
        page: Page,
        filepath: Path,
        timeout_sec: int,
        custom_prompt_path: Path | None = None,
        rel_path: Path | None = None,
    ) -> str:
        """Send a prompt file to chat.qwen.ai and return the full AI response as text.

        Pure orchestration: navigate → auth check → inject → upload → send →
        stream. The caller provides the Playwright page (from browser_session or
        a test fixture).
        """
        emitter = self._emitter()
        try:
            prompt = filepath.read_text(encoding="utf-8").strip()
        except OSError as e:
            raise QwenCliError(f"Failed to read prompt file {filepath}: {e}") from e

        role_prompt = load_role_prompt(filepath, custom_prompt_path, rel_path)
        if role_prompt:
            prompt = f"{role_prompt}\n\n{prompt}"

        self._browser.navigate_to_chat(page, emitter)
        self._browser.check_auth(page)

        self._observability.get_logger().info("Sending prompt to chat.qwen.ai (%d chars)", len(prompt))
        msg_count_before = self._sender.count_messages(page)

        self._injector.find_input(page)
        attached = self._uploader.upload_attachment(page, filepath, emitter=emitter, web_loaded=HeadlessFlag(True))
        if not attached:
            self._observability.get_logger().warning(
                "File upload failed, proceeding with text-only prompt: %s", filepath.name
            )
            emitter.emit(EVENT_DOCUMENT_PARSED, {"file": str(filepath), "char_count": len(prompt)})
        self._injector.inject_text(page, PromptText(prompt))
        self._sender.click_send(page, emitter, document_parsed=HeadlessFlag(True))
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, {"file": str(filepath)})

        response = self._streamer.wait_for_response(
            page,
            TimeoutSec(timeout_sec),
            MessageCount(msg_count_before),
            emitter,
            dispatch_acknowledged=HeadlessFlag(True),
        )

        if response and len(response.strip()) > 0:
            self._observability.get_logger().info("Received response (%d chars)", len(response))
            emitter.emit(EVENT_OUTPUT_COPIED, {"file": str(filepath), "char_count": len(response.strip())})
            return response.strip()
        raise TimeoutError(f"Timeout after {timeout_sec}s: no response detected")

    # ─── Private orchestration helpers (Block 3) ─────────────────
    def _execute(self, fn: Callable[[], ResponseText]) -> ResponseText:
        """Wrap a callable with try/except → error response envelope.

        Eliminates duplicated try/except across public aggregate methods.
        """
        try:
            return fn()
        except Exception as exc:  # boundary: convert any failure into an error response envelope
            return to_error_response(exc)

    def _execute_with_cleanup(
        self,
        fn: Callable[[], ResponseText],
        cleanup: Callable[[], None] | None = None,
    ) -> ResponseText:
        """Wrap a callable with try/except → error response envelope and optional cleanup.

        Eliminates duplicated try/except/finally across public aggregate methods.
        """
        try:
            return fn()
        except Exception as exc:  # boundary: convert any failure into an error response envelope
            return to_error_response(exc)
        finally:
            if cleanup is not None:
                cleanup()

    def _send_file(
        self,
        filepath: Path,
        timeout_sec: int,
        custom_prompt_path: Path | None,
        rel_path: Path | None,
        cfg: AppConfig | None = None,
    ) -> str:
        """Send a prompt file and return the AI response text."""
        active_cfg = cfg or build_app_config(
            mode="single",
            input_path=filepath,
            output_path=DEFAULT_OUTPUT,
            headless=True,
        )

        with self._browser.browser_session(active_cfg) as bctx:
            page = bctx.pages[0] if bctx.pages else bctx.new_page()
            return self.send_file(page, filepath, timeout_sec, custom_prompt_path, rel_path)

    def _emitter(self) -> LifecycleEmitter:
        return LifecycleEmitter(self._observability.get_logger())

    def _process_file(
        self,
        proc_file: Path,
        rel_path: Path,
        cfg: AppConfig,
        ctx: RunContext,
    ) -> None:
        """Process a single file with retry and quarantine handling."""
        out_path, done_path, fail_path, _ = resolve_role_paths(rel_path, cfg)

        if self._cb.is_tripped:
            raise CircuitBreakerOpenError(
                f"Circuit breaker tripped ({cfg.circuit_breaker_threshold} consecutive failures in "
                f"{cfg.circuit_breaker_window}s). Aborting {rel_path}"
            )

        prompt = proc_file.read_text(encoding="utf-8").strip()
        log = self._observability.get_logger()
        log.info("processing_file", file=str(rel_path), chars=len(prompt))
        t0 = time.time()
        self._audit.log_step(ctx, "START_PROCESSING", FilePath(str(rel_path)), "STARTED", {"input_chars": len(prompt)})

        try:
            self._execute_single_attempt(proc_file, rel_path, cfg, ctx, t0, prompt, out_path, done_path)
        except AuthRequiredError:
            raise
        except Exception as exc:  # boundary: quarantine the file on any unexpected failure
            self._handle_processing_failure(proc_file, rel_path, cfg, ctx, t0, prompt, out_path, fail_path, exc)

    def _execute_single_attempt(
        self,
        proc_file: Path,
        rel_path: Path,
        cfg: AppConfig,
        ctx: RunContext,
        t0: float,
        prompt: str,
        out_path: Path,
        done_path: Path,
    ) -> str:
        """Execute a single attempt to process a file."""
        self._rl.acquire()

        role_prompt = load_role_prompt(proc_file, cfg.prompt_file, rel_path)
        full_prompt = f"{role_prompt}\n\n{prompt}" if role_prompt else prompt

        text = self._send_file(proc_file, cfg.request_timeout, cfg.prompt_file, rel_path, cfg)
        dur = time.time() - t0

        text = strip_input_from_output(text, full_prompt)

        self._cb.record_success()
        self._saver.write_output(
            out_path, ResponseText(text), ctx, FilePath(str(rel_path)), dur, len(prompt), OutputChars(len(text))
        )
        self._audit.log(
            "SUCCESS", ctx, FilePath(str(rel_path)), FilePath(str(out_path)), dur, len(prompt), OutputChars(len(text))
        )
        self._audit.log_step(
            ctx,
            "PROCESS_SUCCESS",
            FilePath(str(rel_path)),
            "SUCCESS",
            {"duration_sec": dur, "output_chars": len(text)},
        )

        if out_path.resolve() == done_path.resolve():
            with contextlib.suppress(Exception):
                proc_file.unlink()
        else:
            move_file(proc_file, done_path)

        cleanup_empty_dirs(proc_file.parent, cfg.proc_path)
        return text

    def _handle_processing_failure(
        self,
        proc_file: Path,
        rel_path: Path,
        cfg: AppConfig,
        ctx: RunContext,
        t0: float,
        prompt: str,
        out_path: Path,
        fail_path: Path,
        exc: Exception,
    ) -> None:
        """Record failure metrics, update circuit breaker, and quarantine file."""
        dur = time.time() - t0
        self._cb.record_failure()

        err_msg = f"{type(exc).__name__}: {exc}"
        self._audit.log(
            "FAILED",
            ctx,
            FilePath(str(rel_path)),
            FilePath(str(out_path)),
            dur,
            len(prompt),
            OutputChars(0),
            err_msg,
        )
        self._audit.log_step(ctx, "QUARANTINED", FilePath(str(rel_path)), "FAILED", {"error": err_msg})

        if out_path.resolve() != fail_path.resolve() and proc_file.exists():
            move_file(proc_file, fail_path)
        else:
            with contextlib.suppress(Exception):
                proc_file.unlink()

        cleanup_empty_dirs(proc_file.parent, cfg.proc_path)
        self._observability.get_logger().error("file_quarantined", fail_path=str(fail_path), error=str(exc))

    def _iter_todo(self, cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
        """Yield (proc_file, relative_path) tuples for the processing queue."""
        src = cfg.input_path if cfg.input_path.is_dir() else DEFAULT_TODO
        ensure_dir(src)
        ensure_dir(cfg.proc_path)

        if cfg.retry_failed:
            yield from self._iter_todo_retry_failed(cfg)
            return
        if cfg.mode == "single":
            yield from self._iter_todo_single(cfg)
            return
        if cfg.mode == "batch":
            yield from self._iter_todo_batch(src, cfg)
            return
        yield from self._iter_todo_watcher(src, cfg)

    def _yield_and_move(self, src: Path, cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
        """Yield (proc_file, rel_path) after moving each file to processing dir.

        Common logic shared by _iter_todo_retry_failed, _iter_todo_batch,
        and _iter_todo_watcher.  Watcher mode callers should check shutdown
        flags between yields.
        """
        for f in sorted(f for f in src.rglob("*") if should_process_file(f, src)):
            rel_path = f.resolve().relative_to(src.resolve())
            _, _, _, proc_dest = resolve_role_paths(rel_path, cfg)
            try:
                move_to_processing(f, proc_dest)
                yield proc_dest, rel_path
            except OSError:
                continue

    def _iter_todo_retry_failed(self, cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
        """Yield files for retry-failed mode."""
        src = cfg.failed_path
        if not src.exists() or not src.is_dir():
            return
        yield from self._yield_and_move(src, cfg)

    def _iter_todo_single(self, cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
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
        move_to_processing(cfg.input_path, proc_file)
        yield proc_file, rel_path

    def _iter_todo_batch(self, src: Path, cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
        """Yield files for batch mode."""
        yield from self._yield_and_move(src, cfg)

    def _iter_todo_watcher(self, src: Path, cfg: AppConfig) -> Iterator[tuple[Path, Path]]:
        """Yield files continuously in watcher mode."""
        self._install_watcher_signal_handlers()
        while True:
            for proc_dest, rel_path in self._yield_and_move(src, cfg):
                if _watcher_shutdown.is_set():
                    return
                yield proc_dest, rel_path
            if _watcher_shutdown.is_set():
                return
            _watcher_sleep(cfg.interval)

    def _install_watcher_signal_handlers(self) -> None:
        """Register SIGINT/SIGTERM handlers that request watcher shutdown."""
        log = self._observability.get_logger()

        def _handle_signal(signum: int, _frame: object) -> None:
            log.info("watcher_shutdown_requested", signal=signum)
            _watcher_shutdown.set()

        try:
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except (OSError, ValueError):
            pass
