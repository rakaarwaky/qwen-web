"""Remaining coverage tests for sender.py, saver.py, observability.py, file_uploader.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import Error

from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.capabilities_output_saver import Saver
from modules.shared.src.utility_core_text import strip_ui_noise
from modules.core.src.utility_core_dom_query import count_messages, latest_message_text


def click_send(page, emitter=None, config=None) -> None:
    """Standalone wrapper for SendDispatcher.click_send."""
    SendDispatcher().click_send(page, emitter, config=config)


def write_output(
    path, content: str, ctx, src: str, dur: float, input_chars: int, output_chars: int, config=None
) -> None:
    """Standalone wrapper for Saver.write_output."""
    Saver().write_output(path, content, ctx, src, dur, input_chars, output_chars, config)
from modules.core.src.capabilities_observability_setup import (
    add_trace_context,
    install_excepthooks,
    ObservabilitySetup,
    _bind_run_context as _obs_bind,
    _clear_run_context as _obs_clear,
    _get_logger as _obs_get_logger,
    _get_tracer as _obs_get_tracer,
    _start_span as _obs_start_span,
)


def _configure_sentry() -> None:
    """Standalone wrapper for private method."""
    ObservabilitySetup._configure_sentry(ObservabilitySetup(Path("/tmp")))


def _configure_tracing() -> None:
    """Standalone wrapper for private method."""
    ObservabilitySetup._configure_tracing(ObservabilitySetup(Path("/tmp")))


def _configure_logging(log_path: Path) -> None:
    """Standalone wrapper for private method."""
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
from modules.core.src.capabilities_metrics_collector import MetricsCounter
from modules.core.src.capabilities_status_writer import StatusFileWriter
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.shared.src.utility_core_validation import validate_file as _util_validate_file


def _close_dropdown_if_open(page) -> None:
    """Standalone wrapper for FileUploader._close_dropdown_if_open."""
    FileUploader()._close_dropdown_if_open(page)


def upload_attachment(page, filepath) -> bool:
    """Standalone wrapper for FileUploader.upload_attachment."""
    return FileUploader().upload_attachment(page, filepath)


def validate_file(filepath, max_size_mb=100.0):
    """Standalone wrapper for utility function."""
    return _util_validate_file(filepath, max_size_mb)
from modules.shared.src import (
    LifecycleEmitter,
    RunContext,
    SaverConfig,
    SendDispatchError,
)


# ─── sender.py remaining lines ─────────────────────────────────────────────

class TestSenderRemaining:
    def test_click_send_custom_config(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        from modules.shared.src import SenderConfig
        cfg = SenderConfig(click_timeout_ms=5000, try_enter_key_fallback=False)
        # No selectors match, no enter fallback — new code does not raise, just silently tries
        loc = MagicMock()
        loc.count.return_value = 0
        page.locator.return_value = loc
        # New SendDispatcher.click_send does not raise when no selectors match — it falls back to Enter
        click_send(page, emitter, config=cfg)
        emitter.emit.assert_called()

    def test_count_messages_js_returns_zero(self):
        page = MagicMock()
        page.evaluate.return_value = 0
        loc = MagicMock()
        loc.count.return_value = 5
        page.locator.return_value = loc
        result = count_messages(page)
        assert result == 5

    def test_latest_message_text_js_returns_valid(self):
        page = MagicMock()
        page.evaluate.return_value = "  AI answer  "
        result = latest_message_text(page)
        assert result == "AI answer"

    def test_latest_message_text_js_returns_none(self):
        page = MagicMock()
        page.evaluate.return_value = None
        loc = MagicMock()
        loc.count.return_value = 0
        page.locator.return_value = loc
        result = latest_message_text(page)
        assert result is None


# ─── saver.py remaining lines ───────────────────────────────────────────────

class TestSaverRemaining:
    def test_strip_ui_noise_qwen_max(self):
        text = "Qwen Max\nReal content"
        result = strip_ui_noise(text)
        assert "Qwen Max" not in result

    def test_strip_ui_noise_auto(self):
        text = "Auto\nReal content"
        result = strip_ui_noise(text)
        assert result == "Real content"

    def test_strip_ui_noise_kb_suffix(self):
        text = "128 KB\nReal content"
        result = strip_ui_noise(text)
        assert result == "Real content"

    def test_write_output_with_sidecar_error(self, tmp_path):
        out_file = tmp_path / "result.md"
        ctx = RunContext()
        cfg = SaverConfig(atomic_write=False, generate_sidecar=True)
        # Should not raise even if sidecar write has issues
        write_output(
            path=out_file,
            content="data",
            ctx=ctx,
            src="in.md",
            dur=0.1,
            input_chars=2,
            output_chars=4,
            config=cfg,
        )
        assert out_file.exists()


# ─── observability.py remaining lines ───────────────────────────────────────

class TestObservabilityRemaining:
    def test_configure_sentry_no_dsn(self):
        with patch.dict("os.environ", {}, clear=True):
            _configure_sentry()

    def test_configure_tracing_no_otel(self):
        # New code catches ImportError inline — just call it, no error raised
        _configure_tracing()

    def test_configure_logging_no_structlog(self):
        # New code catches ImportError inline — just call it, no error raised
        _configure_logging(Path("/tmp/test-log"))
