"""Agent: core feature orchestrator (AES405).

Orchestration-only layer. Coordinates capabilities through protocol ABCs —
zero direct I/O, zero business logic, zero domain computation. Implements
ICoreAggregate, consumed by the CLI/MCP surfaces.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_config_factory import build_app_config
from modules.core.src.utility_core_dom_query import latest_message_text
from modules.core.src.utility_core_error_mapping import to_error_response
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
    CHAT_URL,
    DEFAULT_OUTPUT,
    DEFAULT_TODO,
)
from modules.shared.src.taxonomy_core_entity import (
    CircuitBreaker,
    LifecycleEmitter,
    LifecycleGate,
    LifecycleState,
    RateLimiter,
)
from modules.shared.src.taxonomy_core_error import (
    AuthRequiredError,
    QwenCliError,
    ResponseDetectionTimeoutError,
    UploadFailureError,
)
from modules.shared.src.taxonomy_core_event import (
    EVENT_DOCUMENT_PARSED,
    EVENT_FILE_UPLOADED,
    EVENT_PROMPT_INJECTED,
    PIPELINE_EVENT_SEQUENCE,
    LifecycleEvent,
    QwenEventType,
)
from modules.shared.src.taxonomy_core_vo import (
    FailureThreshold,
    FilePath,
    HeadlessFlag,
    MaxPerMinute,
    MessageCount,
    OutputChars,
    PollIntervalSec,
    PromptText,
    ResponseText,
    RunContext,
    TimeoutSec,
    WindowSec,
)
from modules.shared.src.utility_core_prompt import load_role_prompt


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
        """Process one prompt file using the standard move-based queue flow."""
        in_p = Path(input_file).resolve()
        if not in_p.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        cfg = build_app_config(
            mode="single",
            input_path=in_p,
            output_path=Path(output_file).resolve() if output_file else DEFAULT_OUTPUT / in_p.name,
            headless=headless,
        )
        return self._process_single_with_config(cfg)

    def process_mode(self, cfg: AppConfig) -> ResponseText:
        """Dispatch execution for the given AppConfig."""
        return self._process_single_with_config(cfg)

    def _process_single_with_config(self, cfg: AppConfig) -> ResponseText:
        """Process a prompt file and optional attachment directly in-place."""
        prompt_file = cfg.prompt_path or cfg.input_path
        if not prompt_file.exists():
            raise FileNotFoundError(f"Input file not found: {prompt_file}")
        self._apply_runtime_config(cfg)
        ctx = RunContext()

        def _fn() -> ResponseText:
            t0 = time.time()
            text = self._send_file(prompt_file, cfg.request_timeout, cfg.prompt_file, None, cfg)
            dur = time.time() - t0
            prompt_len = prompt_file.stat().st_size if prompt_file.exists() else 0
            out_path = cfg.output_path
            if out_path.is_dir():
                out_path = out_path / f"{prompt_file.stem}_output.md"
            self._saver.write_output(
                out_path,
                ResponseText(text),
                ctx,
                FilePath(str(prompt_file)),
                dur,
                prompt_len,
                OutputChars(len(text)),
            )
            return ResponseText(f"Successfully processed {prompt_file.name} -> {out_path}")

        return self._execute(_fn)

    def _apply_runtime_config(self, cfg: AppConfig) -> None:
        """Apply config-owned limits through the injected runtime collaborators."""
        self._cb.configure(FailureThreshold(cfg.circuit_breaker_threshold), WindowSec(cfg.circuit_breaker_window))
        self._rl.configure(MaxPerMinute(cfg.rate_limit_per_minute))

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
            return ResponseText(self._send_file(Path(tmp_path), timeout_sec, None, None, cfg))

        def _cleanup() -> None:
            p = Path(tmp_path)
            if p.exists():
                p.unlink()

        return self._execute_with_cleanup(_fn, _cleanup)

    def setup_session(
        self,
        wait_for_confirmation: Callable[[], None] | None = None,
        session_path: Path | None = None,
    ) -> ResponseText:
        """Validate or establish a persistent manual login session.

        An existing profile is checked in a temporary headless context first.
        Only a missing or invalid session starts the visible login flow. When a
        CLI surface supplies ``wait_for_confirmation``, that callback runs
        while the visible browser context is still open; this is important for
        manual login and CAPTCHA completion.
        """
        cfg = build_app_config(
            mode="login",
            input_path=DEFAULT_TODO,
            output_path=DEFAULT_OUTPUT,
            session_path=session_path,
            headless=False,
        )

        if cfg.session_path.is_dir() and self._validate_saved_session(cfg):
            return ResponseText("An existing saved Qwen session is already valid. No visible browser was opened.")

        with self._browser.browser_session(cfg) as bctx:
            page = bctx.pages[0] if bctx.pages else bctx.new_page()
            page.goto(CHAT_URL, wait_until="domcontentloaded")

            # For manual login (mode='login'), keep browser open until user closes it.
            # No ENTER press needed — user clicks X on browser window to trigger check.
            # A supplied wait_for_confirmation callback runs on each poll while the
            # visible browser context is still open (manual login / CAPTCHA completion).
            deadline = time.monotonic() + cfg.timeout
            while True:
                if callable(wait_for_confirmation):
                    wait_for_confirmation()
                try:
                    if page.is_closed():
                        break
                except Exception:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    page.wait_for_timeout(min(500, max(1, int(remaining * 10))))
                except Exception:
                    break

        # After user closes the headed browser, validate the saved session in a new
        # headless context (same approach as _validate_saved_session).
        if self._validate_saved_session(cfg):
            return ResponseText("Manual login completed successfully. The Qwen session is valid for headless tasks.")

        return ResponseText(
            "Manual login did not produce a valid Qwen session. Please run 'qwen-web-cli --login' "
            "again and finish the login or CAPTCHA."
        )

    def validate_session(self, session_path: Path | None = None) -> tuple[bool, str]:
        cfg = build_app_config(
            mode="session-check",
            input_path=DEFAULT_TODO,
            output_path=DEFAULT_OUTPUT,
            session_path=session_path,
            headless=True,
        )
        if not cfg.session_path.is_dir():
            return False, "Session tidak ditemukan. Silakan login terlebih dahulu."
        if self._validate_saved_session(cfg):
            return True, "Session tersimpan valid dan siap digunakan."
        return False, "Session tersimpan tidak valid. Silakan login ulang."

    def delete_session(self, session_path: Path | None = None) -> ResponseText:
        cfg = build_app_config(
            mode="session-check",
            input_path=DEFAULT_TODO,
            output_path=DEFAULT_OUTPUT,
            session_path=session_path,
            headless=True,
        )
        if not cfg.session_path.exists():
            return ResponseText("Tidak ada session yang dapat dihapus.")
        try:
            import shutil

            shutil.rmtree(cfg.session_path)
            return ResponseText("Session berhasil dihapus.")
        except Exception as exc:
            raise QwenCliError(f"Gagal menghapus session: {exc}") from exc

    def _validate_saved_session(self, cfg: AppConfig) -> bool:
        """Check an existing profile without opening a visible login window."""
        validation_cfg = build_app_config(
            mode="session-check",
            input_path=DEFAULT_TODO,
            output_path=DEFAULT_OUTPUT,
            session_path=cfg.session_path,
            headless=True,
        )
        try:
            with self._browser.browser_session(validation_cfg) as bctx:
                page = bctx.pages[0] if bctx.pages else bctx.new_page()
                emitter = self._emitter()
                self._browser.navigate_to_chat(page, emitter)
                return self._browser.check_session(page)
        except Exception as exc:  # an expired/corrupt profile should enter manual login
            self._observability.get_logger().debug("saved_session_validation_failed", error=str(exc))
            return False

    def _wait_for_session(self, page: Page, timeout_sec: int) -> None:
        """Wait for a non-CLI manual login flow to become authenticated."""
        deadline = time.monotonic() + timeout_sec
        while not self._browser.check_session(page):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AuthRequiredError(
                    f"Manual login was not completed within {timeout_sec}s. "
                    "Run the login flow again and finish the login or CAPTCHA."
                )
            try:
                page.wait_for_timeout(min(1000, max(1, int(remaining * 1000))))
            except Exception as exc:  # the user may close the browser during manual setup
                raise AuthRequiredError(
                    "The manual-login browser was closed before the Qwen session was verified."
                ) from exc

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
        cfg: AppConfig | None = None,
        emitter: LifecycleEmitter | None = None,
    ) -> str:
        """Send a prompt file while enforcing event-backed lifecycle gates."""
        active_cfg = cfg or build_app_config(
            mode="single",
            input_path=filepath,
            output_path=DEFAULT_OUTPUT,
            headless=True,
        )
        logger = self._observability.get_logger()
        state = LifecycleState()
        gate = LifecycleGate(logger)
        emitter = emitter or LifecycleEmitter(logger, gate=gate)
        for lifecycle_event in PIPELINE_EVENT_SEQUENCE:

            def mark_lifecycle_event(
                _event: LifecycleEvent,
                name: QwenEventType = lifecycle_event,
            ) -> None:
                state.mark(name)

            emitter.on(lifecycle_event, mark_lifecycle_event)
        try:
            prompt = filepath.read_text(encoding="utf-8").strip()
        except OSError as e:
            raise QwenCliError(f"Failed to read prompt file {filepath}: {e}") from e

        role_prompt = load_role_prompt(filepath, custom_prompt_path, rel_path)
        if role_prompt:
            prompt = f"{role_prompt}\n\n{prompt}"

        self._browser.navigate_to_chat(page, emitter)
        if not state.web_loaded:
            raise RuntimeError("Cannot upload attachment: web page loading (EVENT_WEB_LOADED) is incomplete")
        self._browser.check_auth(page)

        self._observability.get_logger().info("Sending prompt to chat.qwen.ai (%d chars)", len(prompt))
        msg_count_before = self._sender.count_messages(page)

        self._injector.find_input(page)
        upload_target = active_cfg.file_path if active_cfg.file_path is not None else filepath
        if upload_target is not None and upload_target.exists():
            if active_cfg.inline_prompt:
                file_size = upload_target.stat().st_size
                emitter.emit(
                    EVENT_FILE_UPLOADED,
                    {"file": str(upload_target), "byte_count": file_size, "transport": "inline_text"},
                )
                emitter.emit(
                    EVENT_DOCUMENT_PARSED,
                    {"file": str(upload_target), "byte_count": file_size, "transport": "inline_text"},
                )
            else:
                attached = self._uploader.upload_attachment(
                    page, upload_target, emitter=emitter, web_loaded=HeadlessFlag(state.web_loaded)
                )
                if not attached or not state.file_uploaded:
                    upload_error = getattr(self._uploader, "last_error", None)
                    detail = f": {upload_error}" if upload_error else ""
                    logger.error("File upload could not be positively verified: %s%s", upload_target.name, detail)
                    raise UploadFailureError(
                        f"Attachment upload failed or was not verified for {upload_target.name}{detail}; "
                        "EVENT_FILE_UPLOADED was not emitted"
                    )
        else:
            emitter.emit(EVENT_FILE_UPLOADED, {"file": "none"})
            emitter.emit(EVENT_DOCUMENT_PARSED, {"file": "none"})

        
        try:
            baseline_response = latest_message_text(page)
        except Exception:
            baseline_response = None
        self._injector.inject_text(page, PromptText(prompt))
        emitter.emit(EVENT_PROMPT_INJECTED, {"file": str(filepath), "char_count": len(prompt)})

        self._sender.click_send(page, emitter, document_parsed=HeadlessFlag(state.document_parsed))
        if not state.dispatch_acknowledged:
            raise RuntimeError("Cannot wait for response: prompt dispatch (EVENT_DISPATCH_ACKNOWLEDGED) is incomplete")

        stream_timeout_sec = min(timeout_sec, active_cfg.streaming_timeout)
        response = self._streamer.wait_for_response(
            page,
            TimeoutSec(stream_timeout_sec),
            MessageCount(msg_count_before),
            emitter,
            polling_interval_sec=PollIntervalSec(active_cfg.poll_interval),
            dispatch_acknowledged=HeadlessFlag(state.dispatch_acknowledged),
            baseline_text=baseline_response,
        )

        if response and len(response.strip()) > 0:
            logger.info("Received response (%d chars)", len(response))
            return response.strip()
        raise ResponseDetectionTimeoutError(
            f"Response detection timeout after {stream_timeout_sec}s: no response detected"
        )

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
        emitter: LifecycleEmitter | None = None,
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
            return self.send_file(
                page, filepath, timeout_sec, custom_prompt_path, rel_path, active_cfg, emitter=emitter
            )

    def _emitter(self) -> LifecycleEmitter:
        return LifecycleEmitter(self._observability.get_logger())
