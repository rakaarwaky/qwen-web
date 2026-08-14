from __future__ import annotations

from pathlib import Path

from modules.core.src.agent_core_orchestrator import CoreOrchestrator
from modules.shared.src import AppConfig


def _orchestrator(mocker) -> CoreOrchestrator:
    return CoreOrchestrator(
        browser=mocker.MagicMock(),
        injector=mocker.MagicMock(),
        sender=mocker.MagicMock(),
        streamer=mocker.MagicMock(),
        uploader=mocker.MagicMock(),
        saver=mocker.MagicMock(),
        audit=mocker.MagicMock(),
        observability=mocker.MagicMock(),
        workspace=mocker.MagicMock(),
    )


def _config(tmp_path: Path, mode: str, input_path: Path, output_path: Path) -> AppConfig:
    return AppConfig(
        mode=mode,
        input_path=input_path,
        output_path=output_path,
        done_path=tmp_path / "done",
        failed_path=tmp_path / "failed",
        proc_path=tmp_path / "processing",
        session_path=tmp_path / "session",
        log_path=tmp_path / "log",
        timeout=37,
        request_timeout=23,
        streaming_timeout=29,
        poll_interval=0.75,
        headless=True,
    )


def test_public_batch_reports_failed_item_as_failed(mocker, tmp_path: Path) -> None:
    cfg = _config(tmp_path, "batch", tmp_path / "input", tmp_path / "output")
    orchestrator = _orchestrator(mocker)
    queued = (tmp_path / "processing" / "role-a" / "task.md", Path("role-a/task.md"))
    orchestrator._iter_todo = mocker.MagicMock(return_value=[queued])
    orchestrator._process_file = mocker.MagicMock(side_effect=RuntimeError("browser failed"))

    result = orchestrator.process_mode(cfg)

    assert "Successfully processed: 0" in result
    assert "Failed: 1" in result


def test_public_single_failure_is_not_success(mocker, tmp_path: Path) -> None:
    source = tmp_path / "input" / "role-a" / "todo" / "task.md"
    source.parent.mkdir(parents=True)
    source.write_text("prompt", encoding="utf-8")
    cfg = _config(tmp_path, "single", source, tmp_path / "output" / "result.md")
    orchestrator = _orchestrator(mocker)
    proc_file = tmp_path / "processing" / "role-a" / "task.md"
    orchestrator._iter_todo = mocker.MagicMock(return_value=[(proc_file, Path("role-a/todo/task.md"))])
    orchestrator._process_file = mocker.MagicMock(side_effect=RuntimeError("browser failed"))

    result = orchestrator.process_mode(cfg)

    assert str(result).startswith("ERROR [RuntimeError]: browser failed")
    assert "Successfully processed" not in result


def test_public_batch_preserves_nested_role_routing(mocker, tmp_path: Path) -> None:
    source = tmp_path / "input" / "role-architect" / "nested" / "deep" / "task.md"
    source.parent.mkdir(parents=True)
    source.write_text("prompt", encoding="utf-8")
    cfg = _config(tmp_path, "batch", tmp_path / "input", tmp_path / "output")
    orchestrator = _orchestrator(mocker)
    orchestrator._process_file = mocker.MagicMock()

    result = orchestrator.process_mode(cfg)

    assert "Successfully processed: 1" in result
    proc_file, rel_path = orchestrator._process_file.call_args.args[:2]
    assert rel_path == Path("role-architect/nested/deep/task.md")
    assert proc_file == cfg.proc_path / "role-architect" / "nested" / "deep" / "task.md"
    assert not source.exists()


def test_public_mode_preserves_custom_paths_and_runtime_controls(mocker, tmp_path: Path) -> None:
    cfg = _config(tmp_path, "batch", tmp_path / "custom-input", tmp_path / "custom-output")
    orchestrator = _orchestrator(mocker)
    orchestrator._iter_todo = mocker.MagicMock(return_value=[])

    result = orchestrator.process_mode(cfg)

    assert "Successfully processed: 0" in result
    orchestrator._browser.browser_session.assert_called_once_with(cfg)
