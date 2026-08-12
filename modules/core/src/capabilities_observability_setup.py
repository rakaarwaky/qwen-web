"""Capabilities: observability stack setup (AES403).

Implements IObservabilityProtocol.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from contextlib import nullcontext, suppress
from pathlib import Path
from typing import Any

from modules.shared.src import utility_core_exit
from modules.shared.src.contract_core_protocol import IObservabilityProtocol
from modules.shared.src.contract_status_protocol import IStatusProtocol
from modules.shared.src.taxonomy_core_vo import ErrorCategory, ExitCode, ServiceName

log = __import__("logging").getLogger("capabilities_observability")

# Block 1: Class Definition & Constructor
class ObservabilitySetup(IObservabilityProtocol):
    """Full observability bootstrap: Sentry → OTel → structlog → hooks."""

    def __init__(self, log_path: Path, status_writer: IStatusProtocol | None = None) -> None:
        self._log_path = log_path
        self._status_path = log_path / "status.json"
        self._status_writer = status_writer

    # ─── Block 2: Public Contract (IObservabilityProtocol ONLY) ──

    def setup_observability(self, log_path: Path | None = None) -> None:
        """Bootstrap observability stack."""
        target_path = log_path or self._log_path
        target_path.mkdir(parents=True, exist_ok=True)
        self._configure_sentry()
        self._configure_tracing()
        self._configure_logging(target_path)
        self._install_excepthooks()

    def _configure_sentry(self) -> None:
        """Configure Sentry (private helper)."""
        try:
            import sentry_sdk
        except ImportError:
            return
        dsn = os.getenv("SENTRY_DSN", "")
        if not dsn:
            return
        with suppress(Exception):
            sentry_sdk.init(
                dsn=dsn,
                environment=os.getenv("ENVIRONMENT", "production"),
                traces_sample_rate=1.0,
            )

    def _configure_tracing(self) -> None:
        """Configure OpenTelemetry tracing (private helper)."""
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError:
            return
        try:
            resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", ServiceName("qwen-web"))})
            provider = TracerProvider(resource=resource)
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
                if endpoint:
                    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            except ImportError:
                pass
            trace.set_tracer_provider(provider)
        except (ImportError, RuntimeError):
            pass

    def _configure_logging(self, log_path: Path) -> None:
        """Configure structlog/stdlib logging (private helper)."""
        try:
            import structlog
        except ImportError:
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

    def _install_excepthooks(self) -> None:
        """Install global exception handlers (private helper)."""
        sys.excepthook = _excepthook
        threading.excepthook = _thread_excepthook

    def get_logger(self, name: str = "qwen-web") -> Any:
        return _get_logger(name)

    def get_tracer(self) -> Any:
        return _get_tracer()

    def start_span(self, name: str) -> Any:
        return _start_span(name)

    def bind_run_context(self, run_id: str, **extra: Any) -> None:
        _bind_run_context(run_id, **extra)

    def clear_run_context(self) -> None:
        _clear_run_context()

    def exit_code_for(self, exc: BaseException) -> ExitCode:
        return ExitCode(utility_core_exit.exit_code_for(exc))

    def install_excepthooks(self) -> None:
        """Install global exception handlers."""
        sys.excepthook = _excepthook
        threading.excepthook = _thread_excepthook

    def write_status(self, status: str, mode: str, headless: bool, run_id: str | None = None) -> None:
        """Write status to disk via DI-injected IStatusProtocol."""
        if self._status_writer is not None:
            self._status_writer.write(status=status, mode=mode, headless=headless, run_id=run_id)

# Block 3: Dunder Methods, Factories & Helpers


    def __repr__(self) -> str:
        """Return string representation of ObservabilitySetup."""
        return f"ObservabilitySetup(log_path={self._log_path!r})"


# ─── Module-level helper functions ──────────────────────────────────────────

def _get_logger(name: str = "qwen-web") -> Any:
    """Return a structlog bound logger, falling back to stdlib logging."""
    try:
        import structlog
    except ImportError:
        return logging.getLogger(name)
    if structlog:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def _get_tracer(name: str = "qwen-web") -> Any:
    """Return an OpenTelemetry tracer, or None when tracing unavailable."""
    try:
        from opentelemetry import trace
    except ImportError:
        return None
    if trace is not None:
        return trace.get_tracer(name)
    return None


def _start_span(name: str) -> Any:
    """Context manager for an OTel span; yields None (no-op) when tracing unavailable."""
    tracer = _get_tracer()
    if tracer is None:
        return nullcontext()
    return tracer.start_as_current_span(name)


def add_trace_context(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Inject active OTel trace_id/span_id into every log event."""
    try:
        from opentelemetry import trace
    except ImportError:
        return event_dict
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
        event_dict["trace_sampled"] = ctx.trace_flags.sampled
    return event_dict


def _bind_run_context(run_id: str, **extra: Any) -> None:
    """Bind run-scoped fields into structlog contextvars."""
    try:
        import structlog
    except ImportError:
        return
    if structlog:
        structlog.contextvars.bind_contextvars(run_id=run_id, **extra)


def _clear_run_context() -> None:
    """Clear all run-scoped contextvars."""
    try:
        import structlog
    except ImportError:
        return
    if structlog:
        structlog.contextvars.clear_contextvars()


def _excepthook(exc_type: type[BaseException], exc_value: BaseException, exc_tb: Any) -> None:
    logger = _get_logger("qwen-web")
    if issubclass(exc_type, KeyboardInterrupt):
        logger.warning("interrupted")
        sys.exit(130)
    logger.critical(
        "unhandled_exception",
        exc_info=(exc_type, exc_value, exc_tb),
        exc_type=exc_type.__name__,
        category=ErrorCategory.categorize(exc_value),
    )
    try:
        import sentry_sdk
    except ImportError:
        pass
    else:
        sentry_sdk.capture_exception(exc_value)
    sys.exit(1)


def _thread_excepthook(args: Any) -> None:
    logger = _get_logger("qwen-web")
    logger.critical(
        "unhandled_exception_in_thread",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        exc_type=args.exc_type.__name__,
        category=ErrorCategory.categorize(args.exc_value),
    )
    try:
        import sentry_sdk
    except ImportError:
        pass
    else:
        sentry_sdk.capture_exception(args.exc_value)


def install_excepthooks() -> None:
    """Install global exception handlers so crashes are logged as structured events."""
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook


def setup_observability(log_path: Path) -> None:
    """Full observability bootstrap."""
    inst = ObservabilitySetup(log_path)
    inst.setup_observability()


def exit_code_for(exc: BaseException) -> ExitCode:
    """Map an unhandled exception to a process exit code (delegates to utility)."""
    return ExitCode(utility_core_exit.exit_code_for(exc))
