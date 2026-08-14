from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from modules.cli.src.surface_cli_run_command import handle


def test_failed_batch_is_not_reported_as_success() -> None:
    core = MagicMock()
    core.process_mode.return_value = "Batch processing complete. Successfully processed: 1, Failed: 1"
    args = SimpleNamespace(_cfg=object())

    result = handle(args, core)

    assert result["success"] is False
    assert result["category"] == "processing_failed"
    assert "Failed: 1" in str(result["error"])


def test_error_processing_response_is_not_reported_as_success() -> None:
    core = MagicMock()
    core.process_mode.return_value = "ERROR [PROCESSING_FAILED]: upload failed"
    args = SimpleNamespace(_cfg=object())

    result = handle(args, core)

    assert result["success"] is False
    assert result["category"] == "processing_failed"


def test_successful_batch_remains_success() -> None:
    core = MagicMock()
    core.process_mode.return_value = "Batch processing complete. Successfully processed: 2, Failed: 0"
    args = SimpleNamespace(_cfg=object())

    result = handle(args, core)

    assert result == {"success": True, "message": core.process_mode.return_value}


def test_missing_config_is_validation_error() -> None:
    result = handle(SimpleNamespace(), MagicMock())

    assert result["success"] is False
    assert result["category"] == "validation_error"
