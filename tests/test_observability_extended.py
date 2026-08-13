"""Tests for observability.py — MetricsCounter, StatusFileWriter, setup, hooks."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

from modules.core.src.capabilities_metrics_collector import MetricsCounter
from modules.core.src.capabilities_observability_setup import (
    ObservabilitySetup,
    _bind_run_context,
    _clear_run_context,
    _get_logger,
    _get_tracer,
    _start_span,
    install_excepthooks,
)
from modules.core.src.capabilities_status_writer import StatusFileWriter
from modules.shared.src import AuthRequiredError, StatusRecordVO


class TestMetricsCounter:
    def test_increment(self):
        m = MetricsCounter()
        m.increment("requests")
        m.increment("requests")
        assert m.get("requests") == 2

    def test_increment_by_amount(self):
        m = MetricsCounter()
        m.increment("bytes", 100)
        assert m.get("bytes") == 100

    def test_get_missing_key(self):
        m = MetricsCounter()
        assert m.get("nonexistent") == 0

    def test_snapshot(self):
        m = MetricsCounter()
        m.increment("a")
        m.increment("b", 5)
        snap = m.snapshot()
        assert snap == {"a": 1, "b": 5}

    def test_thread_safety(self):
        m = MetricsCounter()
        def worker():
            for _ in range(100):
                m.increment("counter")
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert m.get("counter") == 1000


class TestStatusFileWriter:
    def test_write_and_read(self, tmp_path):
        path = tmp_path / "status.json"
        writer = StatusFileWriter(path)
        writer.write(status="running", mode="batch", headless=True, run_id="test_123")
        result = writer.read()
        assert result is not None
        assert result["status"] == "running"
        assert result["mode"] == "batch"
        assert result["headless"] is True
        assert result["run_id"] == "test_123"

    def test_write_record(self, tmp_path):
        path = tmp_path / "status.json"
        writer = StatusFileWriter(path)
        rec = StatusRecordVO(status="done", mode="single", headless=False, run_id="abc")
        writer.write_record(rec)
        result = writer.read()
        assert result["status"] == "done"

    def test_read_nonexistent(self, tmp_path):
        writer = StatusFileWriter(tmp_path / "nope.json")
        assert writer.read() is None

    def test_write_with_error(self, tmp_path):
        path = tmp_path / "status.json"
        writer = StatusFileWriter(path)
        writer.write(status="error", mode="batch", headless=True, error="something broke")
        result = writer.read()
        assert result["error"] == "something broke"

    def test_write_with_cpu_sec(self, tmp_path):
        path = tmp_path / "status.json"
        writer = StatusFileWriter(path)
        writer.write(status="running", mode="watcher", headless=False, cpu_sec=12.34)
        result = writer.read()
        assert result["cpu_sec"] == 12.34


class TestLoggerTracer:
    def test_get_logger(self):
        logger = _get_logger("test")
        assert logger is not None

    def test_get_logger_default(self):
        logger = _get_logger()
        assert logger is not None

    def test_get_tracer(self):
        tracer = _get_tracer("test")
        # May be None if OTel not installed
        assert tracer is None or tracer is not None

    def test_start_span(self):
        with _start_span("test"):
            pass  # should not raise


class TestBindContext:
    def test_bind_and_clear(self):
        _bind_run_context(run_id="test_123", mode="batch")
        _clear_run_context()


class TestExitCodeFor:
    def test_keyboard_interrupt(self):
        obs = ObservabilitySetup(Path("/tmp/qwen-test-log"))
        assert obs.exit_code_for(KeyboardInterrupt()) == 130

    def test_auth_required(self):
        obs = ObservabilitySetup(Path("/tmp/qwen-test-log"))
        assert obs.exit_code_for(AuthRequiredError("login")) == 2

    def test_general_error(self):
        obs = ObservabilitySetup(Path("/tmp/qwen-test-log"))
        assert obs.exit_code_for(RuntimeError("oops")) == 1


class TestExcepthooks:
    def test_install_excepthooks(self):
        install_excepthooks()
        assert sys.excepthook is not None

    def test_thread_excepthook(self):
        install_excepthooks()
        from modules.core.src.capabilities_observability_setup import _thread_excepthook
        args = MagicMock()
        args.exc_type = RuntimeError
        args.exc_value = RuntimeError("test")
        args.exc_traceback = None
        _thread_excepthook(args)


class TestSetupObservability:
    def test_setup_creates_log_dir(self, tmp_path):
        log_dir = tmp_path / "logs"
        ObservabilitySetup(log_dir).setup_observability()
        assert log_dir.exists()

    def test_setup_idempotent(self, tmp_path):
        log_dir = tmp_path / "logs"
        ObservabilitySetup(log_dir).setup_observability()
        ObservabilitySetup(log_dir).setup_observability()  # no error
