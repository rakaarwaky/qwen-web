from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from modules.cli.src.surface_cli_run_command import handle


def _mock_args() -> SimpleNamespace:
    return SimpleNamespace(
        _cfg=SimpleNamespace(
            prompt_path=None,
            input_path=SimpleNamespace(name="PROMPT.md"),
            file_path=None,
            output_path=SimpleNamespace(name="OUTPUT.md"),
            headless=True,
        )
    )


def test_failed_batch_is_not_reported_as_success() -> None:
    core = MagicMock()
    core.process_single_file.return_value = "Batch processing complete. Successfully processed: 1, Failed: 1"
    args = _mock_args()

    result = handle(args, core)

    assert result["success"] is False
    assert result["category"] == "processing_failed"
    assert "Failed: 1" in str(result["error"])


def test_error_processing_response_is_not_reported_as_success() -> None:
    core = MagicMock()
    core.process_single_file.return_value = "ERROR [PROCESSING_FAILED]: upload failed"
    args = _mock_args()

    result = handle(args, core)

    assert result["success"] is False
    assert result["category"] == "processing_failed"


def test_successful_batch_remains_success() -> None:
    core = MagicMock()
    core.process_single_file.return_value = "Batch processing complete. Successfully processed: 2, Failed: 0"
    args = _mock_args()

    result = handle(args, core)

    assert result == {"success": True, "message": core.process_single_file.return_value}


def test_missing_config_is_validation_error() -> None:
    result = handle(SimpleNamespace(), MagicMock())

    assert result["success"] is False
    assert result["category"] == "validation_error"
