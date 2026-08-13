from __future__ import annotations

import errno
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.core.src import agent_core_orchestrator as orchestrator_module
from modules.core.src.agent_core_orchestrator import CoreOrchestrator
from modules.core.src.utility_core_file_mover import move_file
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter


def _make_orchestrator() -> CoreOrchestrator:
    return CoreOrchestrator(
        browser=MagicMock(),
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        uploader=MagicMock(),
        saver=MagicMock(),
        audit=MagicMock(),
        observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
        workspace=MagicMock(),
        circuit_breaker=CircuitBreaker(),
        rate_limiter=RateLimiter(),
    )


def _config(tmp_path: Path, *, mode: str = "batch", input_path: Path | None = None) -> AppConfig:
    return AppConfig(
        mode=mode,
        input_path=input_path or tmp_path / "input",
        output_path=tmp_path / "output",
        done_path=tmp_path / "done",
        failed_path=tmp_path / "failed",
        proc_path=tmp_path / "processing",
        session_path=tmp_path / "session",
        log_path=tmp_path / "log",
        timeout=321,
        request_timeout=17,
        poll_interval=0.75,
        streaming_timeout=23,
        rate_limit_per_minute=7,
        circuit_breaker_threshold=2,
        circuit_breaker_window=11,
        retry_failed=False,
    )


def test_move_file_same_device_uses_replace_and_removes_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.md"
    destination = tmp_path / "nested" / "destination.md"
    source.write_text("payload")
    calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        calls.append((Path(src), Path(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", recording_replace)
    move_file(source, destination)

    assert not source.exists()
    assert destination.read_text() == "payload"
    assert calls == [(source, destination)]


def test_move_file_cross_device_copies_flushes_replaces_then_unlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.md"
    destination = tmp_path / "nested" / "destination.md"
    source.write_text("payload")
    real_replace = os.replace
    calls = 0

    def simulate_cross_device(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError(errno.EXDEV, "cross-device link")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", simulate_cross_device)
    move_file(source, destination)

    assert calls == 2
    assert not source.exists()
    assert destination.read_text() == "payload"
    assert not list(destination.parent.glob(".*.tmp"))


def test_single_public_api_moves_source_and_does_not_report_success_after_quarantine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "role-demo" / "todo" / "task.md"
    source.parent.mkdir(parents=True)
    source.write_text("prompt")
    cfg = _config(tmp_path, mode="single", input_path=source)
    orch = _make_orchestrator()
    orch._browser.browser_session.return_value.__enter__.return_value.pages = [MagicMock()]
    orch._send_file = MagicMock(side_effect=RuntimeError("network down"))
    monkeypatch.setattr(orchestrator_module, "build_app_config", lambda **_kwargs: cfg)

    result = orch.process_single_file(source, cfg.output_path, headless=True)

    failed = cfg.failed_path / "role-demo" / "task.md"
    assert result.startswith("ERROR [PROCESSING_FAILED]")
    assert not source.exists()
    assert failed.exists()
    assert not list(cfg.proc_path.rglob("task.md"))


def test_batch_counts_quarantine_as_failed_and_continues(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    for name in ("failed-first.md", "successful-second.md"):
        path = input_root / "role-demo" / "todo" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name)
    cfg = _config(tmp_path, mode="batch", input_path=input_root)
    orch = _make_orchestrator()
    orch._browser.browser_session.return_value.__enter__.return_value.pages = [MagicMock()]

    def send_file(proc_file: Path, *_args: object, **_kwargs: object) -> str:
        if proc_file.name.startswith("failed"):
            raise RuntimeError("item failed")
        return "response"

    orch._send_file = MagicMock(side_effect=send_file)
    result = orch.process_mode(cfg)

    assert result == "Batch processing complete. Successfully processed: 1, Failed: 1"
    assert (cfg.failed_path / "role-demo" / "failed-first.md").exists()
    assert (cfg.done_path / "role-demo" / "successful-second.md").exists()
    assert not list(input_root.rglob("*.md"))


def test_process_mode_passes_complete_config_and_runtime_limits() -> None:
    orch = _make_orchestrator()
    cfg = _config(Path("/tmp"), mode="batch")
    dispatch = MagicMock(return_value="dispatched")
    orch._process_batch_with_config = dispatch

    assert orch.process_mode(cfg) == "dispatched"
    dispatch.assert_called_once_with(cfg)

    orch._apply_runtime_config(cfg)
    assert orch._cb._threshold == cfg.circuit_breaker_threshold
    assert orch._cb._window_sec == cfg.circuit_breaker_window
    assert orch._rl._max_per_minute == cfg.rate_limit_per_minute


def test_lifecycle_flags_are_event_backed_and_passed_to_capabilities(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("prompt")
    orch = _make_orchestrator()
    page = MagicMock()
    orch._uploader.upload_attachment.return_value = False
    orch._streamer.wait_for_response.return_value = "answer"

    assert orch.send_file(page, prompt_file, timeout_sec=5) == "answer"
    assert orch._uploader.upload_attachment.call_args.kwargs["web_loaded"] is True
    assert orch._sender.click_send.call_args.kwargs["document_parsed"] is True
    assert orch._streamer.wait_for_response.call_args.kwargs["dispatch_acknowledged"] is True
    assert orch._streamer.wait_for_response.call_args.kwargs["polling_interval_sec"] == 1.0


def test_navigation_failure_blocks_upload_and_send(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("prompt")
    orch = _make_orchestrator()
    orch._browser.navigate_to_chat.side_effect = RuntimeError("navigation failed")

    with pytest.raises(RuntimeError, match="navigation failed"):
        orch.send_file(MagicMock(), prompt_file, timeout_sec=5)

    orch._uploader.upload_attachment.assert_not_called()
    orch._sender.click_send.assert_not_called()
    orch._streamer.wait_for_response.assert_not_called()


def test_dispatch_failure_blocks_stream_monitor(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("prompt")
    orch = _make_orchestrator()
    orch._uploader.upload_attachment.return_value = False
    orch._sender.click_send.side_effect = RuntimeError("dispatch failed")

    with pytest.raises(RuntimeError, match="dispatch failed"):
        orch.send_file(MagicMock(), prompt_file, timeout_sec=5)

    orch._streamer.wait_for_response.assert_not_called()
