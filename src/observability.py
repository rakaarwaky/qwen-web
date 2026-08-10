"""Observability stack: structlog + OpenTelemetry + Sentry + global exception hooks.

All types are centralized in src/types.py — import directly from there.
MetricsCounter and StatusFileWriter are behavioral entities defined locally.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import structlog
    has_structlog = True
except ImportError:  # pragma: no cover
    structlog = None  # type: ignore[assignment]
    has_structlog = False

try:
    import sentry_sdk
    has_sentry = True
except ImportError:  # pragma: no cover
    has_sentry = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    has_otel = True
except ImportError:  # pragma: no cover
    trace = None  # type: ignore[assignment]
    has_otel = False

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    has_otlp = True
except ImportError:  # pragma: no cover
    has_otlp = False

from .types import (
    SERVICE_NAME,
    AuthRequiredError,
    ErrorCategory,
    StatusRecord,
)


# ─── Metrics counter ─────────────────────────────────────────────────────────
class MetricsCounter:
    """Simple in-memory metrics collector for request/file stats.

    Thread-safe via threading.Lock.
    """

    def __init__(self) -> None:
        """Initialize with empty counters and a start timestamp."""
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._start_time = datetime.now(tz=timezone.utc)

    def increment(self, key: str, amount: int = 1) -> None:
        """Increment a counter by amount."""
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + amount

    def get(self, key: str) -> int:
        """Get current counter value."""
        with self._lock:
            return self._counters.get(key, 0)

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of all counters."""
        with self._lock:
            return dict(self._counters)


# ─── Status file writer ──────────────────────────────────────────────────────
class StatusFileWriter:
    """Writes a JSON status file that systemd / monitoring tools can read.

    The status file is updated on every major lifecycle event.
    """

    def __init__(self, status_path: Path) -> None:
        """Initialize with the target status file path, creating parent dirs."""
        self._status_path = status_path
        self._status_path.parent.mkdir(parents=True, exist_ok=True)

    def write_record(self, record: StatusRecord) -> None:
        """Atomically write a StatusRecord to disk."""
        self.write(
            status=record.status,
            mode=record.mode,
            headless=record.headless,
            run_id=record.run_id,
            error=record.error,
            cpu_sec=record.cpu_sec,
            files_processed=record.files_processed,
            files_failed=record.files_failed,
        )

    def write(
        self,
        status: str,
        mode: str,
        headless: bool,
        run_id: str | None = None,
        error: str | None = None,
        cpu_sec: float | None = None,
        files_processed: int = 0,
        files_failed: int = 0,
    ) -> None:
        """Atomically write the current status to disk."""
        rec: dict[str, Any] = {
            "status": status,
            "mode": mode,
            "headless": headless,
            "run_id": run_id,
            "files_processed": files_processed,
            "files_failed": files_failed,
        }
        if cpu_sec is not None:
            rec["cpu_sec"] = round(cpu_sec, 2)
        if error:
            rec["error"] = error

        tmp_path = self._status_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(
                json.dumps(rec, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp_path.rename(self._status_path)
        except Exception:
            pass

    def read(self) -> dict[str, Any] | None:
        """Read the last written status file."""
        try:
            res: dict[str, Any] = json.loads(self._status_path.read_text(encoding="utf-8"))
            return res
        except FileNotFoundError:
            return None
        except Exception:
            return None


# ─── Logger / Tracer accessors ────────────────────────────────────────────────
def get_logger(name: str = "qwen-cli") -> Any:
    """Return a structlog bound logger, falling back to stdlib logging."""
    if has_structlog:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def get_tracer(name: str = "qwen-cli") -> Any:
    """Return an OpenTelemetry tracer, or None when tracing is unavailable."""
    if trace is not None and has_otel:
        return trace.get_tracer(name)
    return None


def start_span(name: str) -> Any:
    """Context manager for an OTel span; yields None (no-op) when tracing is unavailable.

    Unhandled exceptions raised inside the block are recorded and marked as
    ERROR on the span automatically by the OpenTelemetry context manager.
    """
    tracer = get_tracer()
    if tracer is None:
        return nullcontext()
    return tracer.start_as_current_span(name)


# ─── structlog processor: log-trace correlation ──────────────────────────────
def add_trace_context(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Inject the active OTel trace_id/span_id (W3C hex) into every log event."""
    if trace is not None:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
            event_dict["trace_sampled"] = ctx.trace_flags.sampled
    return event_dict


# ─── Run-scoped context binding ──────────────────────────────────────────────
def bind_run_context(run_id: str, **extra: Any) -> None:
    """Bind run-scoped fields into structlog contextvars (visible on every log line)."""
    if has_structlog:
        structlog.contextvars.bind_contextvars(run_id=run_id, **extra)


def clear_run_context() -> None:
    """Clear all run-scoped contextvars."""
    if has_structlog:
        structlog.contextvars.clear_contextvars()


# ─── Global exception handlers ───────────────────────────────────────────────
def exit_code_for(exc: BaseException) -> int:
    """Map an unhandled exception to a process exit code."""
    if isinstance(exc, KeyboardInterrupt):
        return 130
    if isinstance(exc, AuthRequiredError):
        return 2
    return 1


def _excepthook(exc_type: type[BaseException], exc_value: BaseException, exc_tb: Any) -> None:
    log = get_logger("qwen-cli")
    if issubclass(exc_type, KeyboardInterrupt):
        log.warning("interrupted")
        sys.exit(130)
    log.critical(
        "unhandled_exception",
        exc_info=(exc_type, exc_value, exc_tb),
        exc_type=exc_type.__name__,
        category=ErrorCategory.categorize(exc_value),
    )
    if has_sentry:
        sentry_sdk.capture_exception(exc_value)
    sys.exit(1)


def _thread_excepthook(args: Any) -> None:
    log = get_logger("qwen-cli")
    log.critical(
        "unhandled_exception_in_thread",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        exc_type=args.exc_type.__name__,
        category=ErrorCategory.categorize(args.exc_value),
    )
    if has_sentry:
        sentry_sdk.capture_exception(args.exc_value)


def install_excepthooks() -> None:
    """Install global exception handlers so crashes are logged as structured events."""
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook


# ─── Setup ────────────────────────────────────────────────────────────────────
def setup_observability(log_path: Path) -> None:
    """Full observability bootstrap: Sentry → OpenTelemetry → structlog → hooks.

    OpenTelemetry MUST be configured before structlog so the trace-context
    processor can see active spans.
    """
    log_path.mkdir(parents=True, exist_ok=True)
    _configure_sentry()
    _configure_tracing()
    _configure_logging(log_path)
    install_excepthooks()


def _configure_sentry() -> None:
    if not has_sentry:
        return
    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        return
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("ENVIRONMENT", "production"),
            traces_sample_rate=1.0,
        )
    except Exception:
        pass


def _configure_tracing() -> None:
    if not has_otel or trace is None:
        return
    try:
        resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", SERVICE_NAME)})
        provider = TracerProvider(resource=resource)
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        if endpoint and has_otlp:
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
    except Exception:
        pass


def _configure_logging(log_path: Path) -> None:
    if not has_structlog or structlog is None:
        logging.basicConfig(level=logging.INFO)
        return

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        add_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    is_dev = os.getenv("ENVIRONMENT", "production") == "development" or sys.stderr.isatty()
    renderer = (
        structlog.dev.ConsoleRenderer(colors=True)
        if is_dev
        else structlog.processors.JSONRenderer(ensure_ascii=False)
    )

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)
    try:
        file_handler = logging.FileHandler(log_path / "app.jsonl", encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        pass
