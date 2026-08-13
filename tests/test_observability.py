"""Unit tests for observability module and status file writer."""

from __future__ import annotations

from pathlib import Path

from modules.core.src.capabilities_observability_setup import MetricsCounter, StatusFileWriter
from modules.shared.src import ObservabilityConfig, StatusRecordVO


def test_metrics_counter():
    counter = MetricsCounter()
    counter.increment("requests")
    counter.increment("requests", 2)
    counter.increment("errors")

    assert counter.get("requests") == 3
    assert counter.get("errors") == 1
    assert counter.get("missing") == 0

    snap = counter.snapshot()
    assert snap == {"requests": 3, "errors": 1}


def test_status_file_writer(tmp_path: Path):
    status_file = tmp_path / "status.json"
    writer = StatusFileWriter(status_file)

    writer.write(
        status="RUNNING",
        mode="batch",
        headless=True,
        run_id="run-123",
        files_processed=5,
    )

    data = writer.read()
    assert data is not None
    assert data["status"] == "RUNNING"
    assert data["mode"] == "batch"
    assert data["run_id"] == "run-123"
    assert data["files_processed"] == 5


def test_status_file_writer_record(tmp_path: Path):
    status_file = tmp_path / "status_record.json"
    writer = StatusFileWriter(status_file)

    rec = StatusRecordVO(
        status="COMPLETED",
        mode="single",
        headless=False,
        run_id="run-456",
        files_processed=1,
        files_failed=0,
    )
    writer.write_record(rec)

    data = writer.read()
    assert data is not None
    assert data["status"] == "COMPLETED"
    assert data["run_id"] == "run-456"


def test_observability_config(tmp_path: Path):
    cfg = ObservabilityConfig(log_path=tmp_path / "logs", environment="test")
    assert cfg.log_path == tmp_path / "logs"
    assert cfg.environment == "test"
    assert cfg.enable_sentry is True
