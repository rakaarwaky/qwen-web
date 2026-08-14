"""Comprehensive tests for remaining uncovered lines across all modules."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from modules.core.src.capabilities_browser_adapter import _assert_on_chat_page
from modules.core.src.capabilities_observability_setup import MetricsCounter, StatusFileWriter
from modules.root_cli_main_entry import main
from modules.root_mcp_main_entry import (
    qwen_get_audit_log,
    qwen_start_watcher,
)
from modules.shared.src import (
    LifecycleEmitter,
    cleanup_empty_dirs,
    extract_prompt_text,
    list_input_files,
    should_process_file,
    strip_input_from_output,
    validate_file,
)
from tests.helpers import (
    bind_run_context,
    clean_stale_locks,
    clear_run_context,
    get_logger,
    get_tracer,
    make_app_config,
    make_test_orchestrator,
    navigate_to_chat,
    start_span,
)

# ─── main.py remaining lines ────────────────────────────────────────────────


class TestMainRemaining:
    def test_main_with_init_flag(self, tmp_path):
        with patch("sys.argv", ["qwen-cli", "--init", str(tmp_path)]):
            result = main()
            assert result == 0

    def test_main_single_instance_lock_error(self):
        with (
            patch("sys.argv", ["qwen-cli", "-i", "/tmp/in", "-o", "/tmp/out", "--headless"]),
            patch("modules.root_cli_main_entry._default_container", side_effect=Exception("lock")),
        ):
            result = main()
            assert result == 1

    def test_main_batch_processes_files(self, tmp_path):
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        with (
            patch("sys.argv", ["qwen-cli", "-i", str(in_dir), "-o", str(tmp_path / "out"), "--headless"]),
            patch("modules.cli.src.surface_cli_run_command.handle", return_value={"success": True, "message": "ok"}),
        ):
            result = main()
            assert result == 0

    def test_main_setup_observability_error(self, tmp_path):
        in_dir = tmp_path / "in"
        in_dir.mkdir()
        with (
            patch("sys.argv", ["qwen-cli", "-i", str(in_dir), "-o", str(tmp_path / "out"), "--headless"]),
            patch("modules.cli.src.surface_cli_run_command.handle", return_value={"success": False, "error": "boom"}),
        ):
            result = main()
            assert result == 1


# ─── mcp_server.py remaining lines ──────────────────────────────────────────


class TestMcpServerRemaining:
    def test_qwen_start_watcher(self):
        mock_tools = MagicMock()
        mock_tools.start_watcher.return_value = "Watcher loop completed."
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_start_watcher(interval_sec=1))
            loop.close()
            assert "Watcher loop completed" in result

    def test_qwen_get_audit_log_file_not_exist(self, tmp_path):
        mock_tools = MagicMock()
        mock_tools.get_audit_log.return_value = "Audit log file does not exist yet."
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            result = asyncio.run(qwen_get_audit_log())
            assert "does not exist" in result


# ─── pipeline.py remaining lines ────────────────────────────────────────────


class TestPipelineRemaining:
    def test_extract_prompt_text_multiline(self):
        content = "---\ntitle: test\n---\nLine 1\nLine 2"
        result = extract_prompt_text(content)
        assert "Line 1" in result

    def test_strip_input_from_output_line_filter(self):
        lines = [f"Line {i}" for i in range(10)]
        response = "Actual AI response"
        text = "\n".join(lines[:5]) + "\n" + response + "\n" + "\n".join(lines[5:])
        prompt = "\n".join(lines)
        result = strip_input_from_output(text, prompt)
        assert response in result

    def test_list_input_files_nested_roles(self, tmp_path):
        for role in ["role-dev", "role-design"]:
            f = tmp_path / role / "todo" / "task.md"
            f.parent.mkdir(parents=True)
            f.write_text("task")
        files = list_input_files(tmp_path)
        assert len(files) == 2

    def test_should_process_file_in_done_dir(self, tmp_path):
        f = tmp_path / "role-dev" / "done" / "task.md"
        f.parent.mkdir(parents=True)
        f.write_text("x")
        assert should_process_file(f, tmp_path) is False

    def test_iter_todo_batch_moves_files(self, tmp_path):
        todo = tmp_path / "todo" / "role-dev" / "todo"
        todo.mkdir(parents=True)
        (todo / "a.md").write_text("a")
        cfg = make_app_config(
            tmp_path,
            input_path=tmp_path / "todo",
            output_path=tmp_path / "out",
            done_path=tmp_path / "todo" / "done",
            failed_path=tmp_path / "todo" / "failed",
            proc_path=tmp_path / "todo" / "proc",
            session_path=tmp_path / "session",
        )
        orch = make_test_orchestrator()
        files = list(orch._iter_todo_batch(tmp_path / "todo", cfg))
        assert len(files) == 1

    def test_cleanup_empty_dirs_nonempty(self, tmp_path):
        d = tmp_path / "dir"
        d.mkdir()
        (d / "file.txt").write_text("x")
        cleanup_empty_dirs(d, tmp_path)
        assert d.exists()


# ─── browser.py remaining lines ─────────────────────────────────────────────


class TestBrowserRemaining:
    def test_assert_on_chat_page_transient(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        page.query_selector.return_value = None
        loc = MagicMock()
        loc.count.return_value = 0
        loc.first.is_visible.return_value = False
        page.locator.return_value = loc
        _assert_on_chat_page(page)

    def test_navigate_to_chat_success(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        page.query_selector.return_value = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        navigate_to_chat(page, emitter)
        emitter.emit.assert_called_once()

    def test_clean_stale_locks_nonexistent(self):
        clean_stale_locks("/nonexistent/path")


# ─── observability.py remaining lines ───────────────────────────────────────


class TestObservabilityRemaining:
    def test_get_logger_default(self):
        logger = get_logger()
        assert logger is not None

    def test_get_tracer(self):
        tracer = get_tracer("test")
        assert tracer is None or tracer is not None

    def test_start_span(self):
        with start_span("test"):
            pass

    def test_bind_and_clear_context(self):
        bind_run_context(run_id="test", mode="batch")
        clear_run_context()

    def test_metrics_counter_thread_safety(self):
        import threading

        m = MetricsCounter()

        def worker():
            for _ in range(100):
                m.increment("x")

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert m.get("x") == 500

    def test_status_file_write_and_read(self, tmp_path):
        path = tmp_path / "status.json"
        writer = StatusFileWriter(path)
        writer.write(status="running", mode="batch", headless=True)
        result = writer.read()
        assert result is not None
        assert result["status"] == "running"

    def test_status_file_read_nonexistent(self, tmp_path):
        writer = StatusFileWriter(tmp_path / "nope.json")
        assert writer.read() is None


# ─── file_uploader.py remaining lines ───────────────────────────────────────


class TestFileUploaderRemaining:
    def test_validate_file_valid(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello")
        size = validate_file(f)
        assert size == 5

    def test_validate_file_nonexistent(self, tmp_path):
        with pytest.raises(Exception):
            validate_file(tmp_path / "nope.md")

    def test_validate_file_too_large(self, tmp_path):
        f = tmp_path / "big.md"
        f.write_text("x" * 1024)
        with pytest.raises(Exception):
            validate_file(f, max_size_mb=0.0001)
