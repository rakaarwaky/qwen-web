"""Tests for pipeline.py — _iter_todo, _process_file, _cleanup_empty_dirs, watcher, retry."""

from __future__ import annotations
import pytest
pytest.skip("Legacy test — agent_core_orchestrator removed in AES migration", allow_module_level=True)

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.core.src.agent_core_orchestrator import (
    CoreOrchestrator,
    _watcher_shutdown,
    _watcher_sleep,
    request_watcher_shutdown,
)
from modules.shared.src import (
    AppConfig,
    CircuitBreaker,
    CircuitBreakerOpenError,
    RateLimiter,
    RunContext,
)
from modules.shared.src.utility_core_path import cleanup_empty_dirs


class TestCleanupEmptyDirs:
    def test_removes_empty_parents(self, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        child = root / "child"
        child.mkdir()
        cleanup_empty_dirs(child, root)
        assert not child.exists()

    def test_stops_at_nonempty_dir(self, tmp_path):
        root = tmp_path / "root"
        child = root / "child"
        child.mkdir(parents=True)
        (child / "file.txt").write_text("x")
        cleanup_empty_dirs(child, root)
        assert child.exists()

    def test_handles_exception(self, tmp_path):
        cleanup_empty_dirs(tmp_path / "nonexistent", tmp_path)


class TestIterTodoRetryFailed:
    def _make_orchestrator(self):
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

    def test_yields_from_failed(self, tmp_path):
        failed = tmp_path / "failed"
        role_dir = failed / "role-dev"
        role_dir.mkdir(parents=True)
        (role_dir / "task.md").write_text("task")

        cfg = AppConfig(
            mode="batch",
            input_path=failed,
            output_path=tmp_path / "out",
            done_path=failed / "done",
            failed_path=failed,
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
            retry_failed=True,
        )
        orch = self._make_orchestrator()
        files = list(orch._iter_todo_retry_failed(cfg))
        assert len(files) == 1

    def test_no_failed_dir(self, tmp_path):
        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "nonexistent",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "nonexistent",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
            retry_failed=True,
        )
        orch = self._make_orchestrator()
        files = list(orch._iter_todo_retry_failed(cfg))
        assert len(files) == 0


class TestIterTodoSingle:
    def _make_orchestrator(self):
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

    def test_yields_single_file(self, tmp_path):
        todo = tmp_path / "todo"
        todo.mkdir()
        task = todo / "task.md"
        task.write_text("hello")

        cfg = AppConfig(
            mode="single",
            input_path=task,
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
        )
        orch = self._make_orchestrator()
        files = list(orch._iter_todo_single(cfg))
        assert len(files) == 1

    def test_missing_file_raises(self, tmp_path):
        cfg = AppConfig(
            mode="single",
            input_path=tmp_path / "nope.md",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
        )
        orch = self._make_orchestrator()
        with pytest.raises(FileNotFoundError):
            list(orch._iter_todo_single(cfg))


class TestIterTodoBatch:
    def _make_orchestrator(self):
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

    def test_yields_batch_files(self, tmp_path):
        todo = tmp_path / "todo"
        role_dir = todo / "role-dev" / "todo"
        role_dir.mkdir(parents=True)
        (role_dir / "a.md").write_text("a")
        (role_dir / "b.md").write_text("b")

        cfg = AppConfig(
            mode="batch",
            input_path=todo,
            output_path=tmp_path / "out",
            done_path=todo / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
        )
        orch = self._make_orchestrator()
        files = list(orch._iter_todo_batch(todo, cfg))
        assert len(files) == 2


class TestIterTodoMain:
    def _make_orchestrator(self):
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

    def test_dispatches_to_retry_failed(self, tmp_path):
        failed = tmp_path / "failed" / "role-dev"
        failed.mkdir(parents=True)
        (failed / "task.md").write_text("task")

        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "input",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
            retry_failed=True,
        )
        orch = self._make_orchestrator()
        files = list(orch._iter_todo(cfg))
        assert len(files) == 1

    def test_dispatches_to_single(self, tmp_path):
        todo = tmp_path / "todo"
        todo.mkdir()
        task = todo / "task.md"
        task.write_text("hello")

        cfg = AppConfig(
            mode="single",
            input_path=task,
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
        )
        orch = self._make_orchestrator()
        files = list(orch._iter_todo(cfg))
        assert len(files) == 1

    def test_dispatches_to_batch(self, tmp_path):
        todo = tmp_path / "todo" / "role-dev" / "todo"
        todo.mkdir(parents=True)
        (todo / "a.md").write_text("a")

        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "todo",
            output_path=tmp_path / "out",
            done_path=tmp_path / "todo" / "done",
            failed_path=tmp_path / "todo" / "failed",
            proc_path=tmp_path / "todo" / "proc",
            session_path=tmp_path / "session",
        )
        orch = self._make_orchestrator()
        files = list(orch._iter_todo(cfg))
        assert len(files) == 1


class TestProcessFile:
    def _make_orchestrator(self, audit=None):
        return CoreOrchestrator(
            browser=MagicMock(),
            injector=MagicMock(),
            sender=MagicMock(),
            streamer=MagicMock(),
            uploader=MagicMock(),
            saver=MagicMock(),
            audit=audit or MagicMock(),
            observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
            workspace=MagicMock(),
            circuit_breaker=CircuitBreaker(),
            rate_limiter=RateLimiter(),
        )

    def test_circuit_breaker_open_raises(self, tmp_path):
        proc_file = tmp_path / "task.md"
        proc_file.write_text("task")

        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "input",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
        )
        audit = MagicMock()
        ctx = RunContext()
        orch = self._make_orchestrator(audit=audit)
        cb = CircuitBreaker(threshold=1, window_sec=30)
        cb.record_failure()  # trip it
        orch._cb = cb

        with pytest.raises(CircuitBreakerOpenError):
            orch._process_file(proc_file, Path("task.md"), cfg, ctx)

    def test_success_flow(self, tmp_path):
        proc_file = tmp_path / "proc" / "task.md"
        proc_file.parent.mkdir(parents=True)
        proc_file.write_text("task")

        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "input",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
        )
        audit = MagicMock()
        ctx = RunContext()
        orch = self._make_orchestrator(audit=audit)
        orch._streamer.wait_for_response.return_value = "AI response"
        orch._uploader.upload_attachment.return_value = True

        orch._process_file(proc_file, Path("task.md"), cfg, ctx)

        # File should be moved to done or output
        assert not proc_file.exists()


class TestWatcherSleep:
    def test_sleep_responsive_to_shutdown(self):
        request_watcher_shutdown()
        _watcher_sleep(10)  # should return immediately
        # Reset for other tests
        _watcher_shutdown.clear()

    def test_normal_sleep(self):
        _watcher_shutdown.clear()
        _watcher_sleep(1)


class TestIterTodoWatcher:
    def _make_orchestrator(self):
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

    def test_yields_and_shutdown(self, tmp_path):
        _watcher_shutdown.clear()

        todo = tmp_path / "todo" / "role-dev" / "todo"
        todo.mkdir(parents=True)
        (todo / "a.md").write_text("a")

        cfg = AppConfig(
            mode="watcher",
            input_path=tmp_path / "todo",
            output_path=tmp_path / "out",
            done_path=tmp_path / "todo" / "done",
            failed_path=tmp_path / "todo" / "failed",
            proc_path=tmp_path / "todo" / "proc",
            session_path=tmp_path / "session",
            interval=1,
        )

        orch = self._make_orchestrator()
        results = []

        def consume():
            for item in orch._iter_todo_watcher(tmp_path / "todo", cfg):
                results.append(item)
                request_watcher_shutdown()

        t = threading.Thread(target=consume)
        t.start()
        t.join(timeout=10)
        assert len(results) >= 1
        _watcher_shutdown.clear()
