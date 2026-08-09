"""Observability stack: structlog + OpenTelemetry + Sentry + global exception hooks.

P8 additions:
  - ErrorCategory : categorize errors for dashboards/alerting.
  - MetricsCounter: simple in-memory counter for request/file stats.
  - StatusFileWriter: moved here from linux.py (status file writer).
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:  # pragma: no cover
    structlog = None  # type: ignore[assignment]
    HAS_STRUCTLOG = False

try:
    import sentry_sdk
    HAS_SENTRY = True
except ImportError:  # pragma: no cover
    HAS_SENTRY = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    HAS_OTEL = True
except ImportError:  # pragma: no cover
    trace = None  # type: ignore[assignment]
    HAS_OTEL = False

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    HAS_OTLP = True
except ImportError:  # pragma: no cover
    HAS_OTLP = False

SERVICE_NAME = "qwen-web-automation"


# ─── Error categorization (P8) ───────────────────────────────────────────────
class ErrorCategory:
    """Categorize errors for dashboards and alerting.

    Categories:
      - auth         : authentication / login / captcha issues
      - network      : connection lost, DNS, timeout
      - rate_limit   : server throttling (HTTP 429, etc.)
      - browser      : browser crash, launch failure, DOM error
      - injection    : prompt injection failed
      - parsing      : Qwen returned unexpected / empty response
      - file_io      : disk read/write errors
      - other        : uncategorized
    """

    @staticmethod
    def categorize(exc: BaseException) -> str:
        """Return the error category string."""
        exc_type = type(exc).__name__
        msg = str(exc).lower()

        if any(k in msg or k in exc_type.lower() for k in ("auth", "login", "captcha", "signin")):
            return "auth"
        if any(k in msg or k in exc_type.lower() for k in ("network", "connection", "timeout", "dns", "socket")):
            return "network"
        if any(k in msg or k in exc_type.lower() for k in ("rate", "limit", "throttl", "429")):
            return "rate_limit"
        if any(k in msg or k in exc_type.lower() for k in ("browser", "launch", "dom", "playwright", "chromium")):
            return "browser"
        if any(k in msg or k in exc_type.lower() for k in ("injection", "paste", "clipboard", "fill")):
            return "injection"
        if any(k in msg or k in exc_type.lower() for k in ("parse", "empty", "no response", "timeout")):
            return "parsing"
        if any(k in msg or k in exc_type.lower() for k in ("file", "io", "disk", "read", "write")):
            return "file_io"
        return "other"


# ─── Metrics counter (P8) ────────────────────────────────────────────────────
class MetricsCounter:
    """Simple in-memory metrics collector for request/file stats.

    Thread-safe via threading.Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._start_time = datetime.now()

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


# ─── Logger / Tracer accessors ───────────────────────────────────────────────
def get_logger(name: str = "qwen-cli") -> Any:
    """Return a structlog bound logger, falling back to stdlib logging."""
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def get_tracer(name: str = "qwen-cli") -> Any:
    """Return an OpenTelemetry tracer, or None when tracing is unavailable."""
    if HAS_OTEL and trace is not None:
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
def add_trace_context(_logger: Any, _method: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
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
    if HAS_STRUCTLOG:
        structlog.contextvars.bind_contextvars(run_id=run_id, **extra)


def clear_run_context() -> None:
    """Clear all run-scoped contextvars."""
    if HAS_STRUCTLOG:
        structlog.contextvars.clear_contextvars()


# ─── Global exception handlers ───────────────────────────────────────────────
def exit_code_for(exc: BaseException) -> int:
    """Map an unhandled exception to a process exit code."""
    if isinstance(exc, KeyboardInterrupt):
        return 130
    from .config import AuthRequiredError
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
    if HAS_SENTRY:
        sentry_sdk.capture_exception(exc_value)  # type: ignore[misc]
    sys.exit(1)


def _thread_excepthook(args: Any) -> None:
    log = get_logger("qwen-cli")
    log.critical(
        "unhandled_exception_in_thread",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        exc_type=args.exc_type.__name__,
        category=ErrorCategory.categorize(args.exc_value),
    )
    if HAS_SENTRY:
        sentry_sdk.capture_exception(args.exc_value)  # type: ignore[misc]


def install_excepthooks() -> None:
    """Install global exception handlers so crashes are logged as structured events."""
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook


# ─── Status file writer (P8) ────────────────────────────────────────────────
class StatusFileWriter:
    """Writes a JSON status file that systemd / monitoring tools can read.

    The status file is updated on every major lifecycle event.
    """

    def __init__(self, status_path: Path) -> None:
        self._status_path = status_path
        self._status_path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        status: str,
        mode: str,
        headless: bool,
        run_id: Optional[str] = None,
        error: Optional[str] = None,
        cpu_sec: Optional[float] = None,
        files_processed: int = 0,
        files_failed: int = 0,
    ) -> None:
        """Atomically write the current status to disk.

        Parameters
        ----------
        status : str
            One of "running", "completed", "failed", "error".
        mode : str
            The active mode: "watcher", "batch", "single".
        headless : bool
            Whether the browser is running headlessly.
        run_id : str, optional
            Current run identifier.
        error : str, optional
            Error message if status is "failed" or "error".
        cpu_sec : float, optional
            Elapsed wall-clock seconds.
        files_processed : int
            Number of successfully processed files.
        files_failed : int
            Number of files that failed processing.
        """
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
            import json

            tmp_path.write_text(
                json.dumps(rec, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp_path.rename(self._status_path)
        except Exception:
            # Non-fatal — best-effort only
            pass

    def read(self) -> Optional[dict[str, Any]]:
        """Read the last written status file."""
        try:
            import json
            return json.loads(self._status_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except Exception:
            return None


# ─── Setup ───────────────────────────────────────────────────────────────────
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
    if not HAS_SENTRY:
        return
    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        return
    try:
        sentry_sdk.init(  # type: ignore[possibly-undefined]
            dsn=dsn,
            environment=os.getenv("ENVIRONMENT", "production"),
            traces_sample_rate=1.0,
        )
    except Exception:
        pass


def _configure_tracing() -> None:
    if not HAS_OTEL or trace is None:
        return
    try:
        resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", SERVICE_NAME)})
        provider = TracerProvider(resource=resource)
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        if endpoint and HAS_OTLP:
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
    except Exception:
        pass


def _configure_logging(log_path: Path) -> None:
    if not HAS_STRUCTLOG or structlog is None:
        logging.basicConfig(level=logging.INFO)
        return

    shared_processors: List[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        add_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    is_dev = os.getenv("ENVIRONMENT", "production") == "development"
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
