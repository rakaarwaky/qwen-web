"""Shared test helpers: standalone wrappers duplicated across test files.

These thin delegates exist only to give each wrapper its own name for pytest
output — the underlying class/function is what actually matters.
"""

from __future__ import annotations

from pathlib import Path

from modules.core.src.capabilities_output_saver import Saver
from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.capabilities_observability_setup import (
    ObservabilitySetup,
    _bind_run_context as _obs_bind,
    _clear_run_context as _obs_clear,
    _get_logger as _obs_get_logger,
    _get_tracer as _obs_get_tracer,
    _start_span as _obs_start_span,
)
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.shared.src.utility_core_validation import validate_file as _util_validate_file
from modules.shared.src import RunContext


def write_output(
    path, content: str, ctx, src: str, dur: float, input_chars: int, output_chars: int, config=None
) -> None:
    """Standalone wrapper for Saver.write_output."""
    Saver().write_output(path, content, ctx, src, dur, input_chars, output_chars, config)


def click_send(page, emitter=None, config=None) -> None:
    """Standalone wrapper for SendDispatcher.click_send."""
    SendDispatcher().click_send(page, emitter, config=config)


def _configure_sentry() -> None:
    """Standalone wrapper for ObservabilitySetup._configure_sentry."""
    ObservabilitySetup._configure_sentry(ObservabilitySetup(Path("/tmp")))


def _configure_tracing() -> None:
    """Standalone wrapper for ObservabilitySetup._configure_tracing."""
    ObservabilitySetup._configure_tracing(ObservabilitySetup(Path("/tmp")))


def _configure_logging(log_path: Path) -> None:
    """Standalone wrapper for ObservabilitySetup._configure_logging."""
    ObservabilitySetup._configure_logging(ObservabilitySetup(Path("/tmp")), log_path)


def bind_run_context(run_id: str, **extra) -> None:
    """Standalone wrapper for private module function."""
    _obs_bind(run_id, **extra)


def clear_run_context() -> None:
    """Standalone wrapper for private module function."""
    _obs_clear()


def get_logger(name="qwen-web"):
    """Standalone wrapper for private module function."""
    return _obs_get_logger(name)


def get_tracer(name="qwen-web"):
    """Standalone wrapper for private module function."""
    return _obs_get_tracer(name)


def start_span(name):
    """Standalone wrapper for private module function."""
    return _obs_start_span(name)


def _close_dropdown_if_open(page) -> None:
    """Standalone wrapper for FileUploader._close_dropdown_if_open."""
    FileUploader()._close_dropdown_if_open(page)


def upload_attachment(page, filepath) -> bool:
    """Standalone wrapper for FileUploader.upload_attachment."""
    return FileUploader().upload_attachment(page, filepath)


def validate_file(filepath, max_size_mb=100.0):
    """Standalone wrapper for utility function."""
    return _util_validate_file(filepath, max_size_mb)
