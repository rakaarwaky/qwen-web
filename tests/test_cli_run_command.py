from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from modules.cli.src.surface_cli_run_command import handle
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG, DEFAULT_OUTPUT, DEFAULT_SESSION


def _cfg(
    mode: str = "single",
    *,
    inline_prompt_text: str | None = None,
    prompt_path: Path | None = None,
    file_path: Path | None = None,
) -> AppConfig:
    """Build an AppConfig matching the subcommand-derived shape used by `main`."""
    dummy = Path("/dev/null")
    is_direct = mode == "direct"
    return AppConfig(
        mode=mode,
        input_path=prompt_path or dummy,
        output_path=DEFAULT_OUTPUT,
        done_path=dummy,
        failed_path=dummy,
        proc_path=dummy,
        session_path=DEFAULT_SESSION,
        log_path=DEFAULT_LOG,
        headless=True,
        prompt_file=prompt_path,
        prompt_path=prompt_path,
        file_path=file_path,
        inline_prompt=is_direct,
        inline_prompt_text=inline_prompt_text if is_direct else None,
    )


def _orchestrators(result: str) -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return (direct, file_only, attachment) mocks all returning ``result``."""
    direct = MagicMock()
    file_only = MagicMock()
    attachment = MagicMock()
    direct.process_direct_prompt.return_value = result
    file_only.process_prompt_file_only.return_value = result
    attachment.process_prompt_with_attachment.return_value = result
    return direct, file_only, attachment


def test_failed_batch_is_not_reported_as_success() -> None:
    result = "Batch processing complete. Successfully processed: 1, Failed: 1"
    direct, file_only, attachment = _orchestrators(result)
    cfg = _cfg()

    out = handle(SimpleNamespace(), cfg, direct, file_only, attachment)

    assert out["success"] is False
    assert out["category"] == "processing_failed"
    assert "Failed: 1" in str(out["error"])


def test_error_processing_response_is_not_reported_as_success() -> None:
    result = "ERROR [PROCESSING_FAILED]: upload failed"
    direct, file_only, attachment = _orchestrators(result)
    cfg = _cfg()

    out = handle(SimpleNamespace(), cfg, direct, file_only, attachment)

    assert out["success"] is False
    assert out["category"] == "processing_failed"


def test_successful_batch_remains_success() -> None:
    result = "Batch processing complete. Successfully processed: 2, Failed: 0"
    direct, file_only, attachment = _orchestrators(result)
    cfg = _cfg()

    out = handle(SimpleNamespace(), cfg, direct, file_only, attachment)

    assert out == {"success": True, "message": result}


def test_missing_config_is_validation_error() -> None:
    # direct mode requires inline prompt text; without it the surface rejects early.
    cfg = _cfg(mode="direct")
    direct, file_only, attachment = _orchestrators("")

    out = handle(SimpleNamespace(), cfg, direct, file_only, attachment)

    assert out["success"] is False
    assert out["category"] == "validation_error"
