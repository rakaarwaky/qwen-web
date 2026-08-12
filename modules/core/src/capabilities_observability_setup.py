"""Capabilities: observability stack setup (AES403).

Implements IObservabilityProtocol.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from contextlib import nullcontext, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.shared.src import utility_core_exit
from modules.shared.src.contract_core_protocol import IObservabilityProtocol
from modules.shared.src.taxonomy_core_vo import ErrorCategory, ExitCode, ServiceName

log = __import__("logging").getLogger("capabilities_observability")


def _module_impl() -> Any:
    """Return this module to call module-level functions from methods."""
    import importlib

    return importlib.import_module(__name__)

# Optional imports
structlog: Any = None
trace: Any = None

try:
    import structlog
    has_structlog = True
except ImportError:
    has_structlog = False

try:
    import sentry_sdk
    has_sentry = True
except ImportError:
    has_sentry = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    has_otel = True
except ImportError:
    has_otel = False

try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    has_otlp = True
except ImportError:
    has_otlp = False


# Re-export from dedicated modules (single-concern files)
from modules.core.src.capabilities_metrics_collector import MetricsCounter  # noqa: F401
from modules.core.src.capabilities_status_writer import StatusFileWriter  # noqa: F401


def get_logger(name: str = "qwen-web") -> Any:
    """Return a structlog bound logger, falling back to stdlib logging."""
    if has_structlog and structlog:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def get_tracer(name: str = "qwen-web") -> Any:
    """Return an OpenTelemetry tracer, or None when tracing unavailable."""
    if trace is not None and has_otel:
        return trace.get_tracer(name)
    return None


def start_span(name: str) -> Any:
    """Context manager for an OTel span; yields None (no-op) when tracing unavailable."""
    tracer = get_tracer()
    if tracer is None:
        return nullcontext()
    return tracer.start_as_current_span(name)


def add_trace_context(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Inject active OTel trace_id/span_id into every log event."""
    if trace is not None:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
            event_dict["trace_sampled"] = ctx.trace_flags.sampled
    return event_dict


def bind_run_context(run_id: str, **extra: Any) -> None:
    """Bind run-scoped fields into structlog contextvars."""
    if has_structlog and structlog:
        structlog.contextvars.bind_contextvars(run_id=run_id, **extra)


def clear_run_context() -> None:
    """Clear all run-scoped contextvars."""
    if has_structlog and structlog:
        structlog.contextvars.clear_contextvars()


class ObservabilitySetup(IObservabilityProtocol):
    """Full observability bootstrap: Sentry → OTel → structlog → hooks."""

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path
        self._status_path = log_path / "status.json"

    def setup_observability(self, log_path: Path | None = None) -> None:
        """Bootstrap observability stack."""
        target_path = log_path or self._log_path
        target_path.mkdir(parents=True, exist_ok=True)
        self._configure_sentry()
        self._configure_tracing()
        self._configure_logging(target_path)
        self._install_excepthooks()

    def _configure_sentry(self) -> None:
        if not has_sentry:
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
        if not has_otel or trace is None:
            return
        try:
            resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", ServiceName("qwen-web"))})
            provider = TracerProvider(resource=resource)
            endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
            if endpoint and has_otlp:
                provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
            trace.set_tracer_provider(provider)
        except Exception:
            pass

    def _configure_logging(self, log_path: Path) -> None:
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

    def _install_excepthooks(self) -> None:
        sys.excepthook = _excepthook
        threading.excepthook = _thread_excepthook

    def get_logger(self, name: str = "qwen-web") -> Any:
        return _module_impl().get_logger(name)

    def get_tracer(self) -> Any:
        return _module_impl().get_tracer()

    def start_span(self, name: str) -> Any:
        return _module_impl().start_span(name)

    def bind_run_context(self, run_id: str, **extra: Any) -> None:
        _module_impl().bind_run_context(run_id, **extra)

    def clear_run_context(self) -> None:
        _module_impl().clear_run_context()

    def exit_code_for(self, exc: BaseException) -> ExitCode:
        return ExitCode(utility_core_exit.exit_code_for(exc))

    def install_excepthooks(self) -> None:
        _module_impl().install_excepthooks()

    def write_status(self, status: str, mode: str, headless: bool, run_id: str | None = None) -> None:
        writer = StatusFileWriter(self._status_path)
        writer.write(status=status, mode=mode, headless=headless, run_id=run_id)


def _excepthook(exc_type: type[BaseException], exc_value: BaseException, exc_tb: Any) -> None:
    logger = get_logger("qwen-web")
    if issubclass(exc_type, KeyboardInterrupt):
        logger.warning("interrupted")
        sys.exit(130)
    logger.critical(
        "unhandled_exception",
        exc_info=(exc_type, exc_value, exc_tb),
        exc_type=exc_type.__name__,
        category=ErrorCategory.categorize(exc_value),
    )
    if has_sentry and sentry_sdk:
        sentry_sdk.capture_exception(exc_value)
    sys.exit(1)


def _thread_excepthook(args: Any) -> None:
    logger = get_logger("qwen-web")
    logger.critical(
        "unhandled_exception_in_thread",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        exc_type=args.exc_type.__name__,
        category=ErrorCategory.categorize(args.exc_value),
    )
    if has_sentry and sentry_sdk:
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


def _configure_sentry() -> None:
    """Configure Sentry (module-level convenience)."""
    ObservabilitySetup(Path("/tmp/qwen-web"))._configure_sentry()


def _configure_tracing() -> None:
    """Configure OpenTelemetry tracing (module-level convenience)."""
    ObservabilitySetup(Path("/tmp/qwen-web"))._configure_tracing()


def _configure_logging(log_path: Path) -> None:
    """Configure structlog/stdlib logging (module-level convenience)."""
    ObservabilitySetup(log_path)._configure_logging(log_path)


# Re-export from dedicated module
from modules.core.src.capabilities_status_writer import get_status_writer  # noqa: F401
