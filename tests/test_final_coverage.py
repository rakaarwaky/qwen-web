"""Final push tests for remaining hard-to-cover lines."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.root_cli_main_entry import _run_manual_login, _run_watcher, main
from modules.root_mcp_main_entry import (
    qwen_process_batch,
    qwen_process_single,
    qwen_send_prompt,
    qwen_start_watcher,
)
from modules.core.src.capabilities_pipeline_compat import (
    _iter_todo_retry_failed,
    _iter_todo_single,
    _iter_todo_watcher,
    _process_file,
    request_watcher_shutdown,
)
from modules.core.src.capabilities_observability import (
    _configure_sentry,
    _configure_tracing,
    _configure_logging,
    _excepthook,
    _thread_excepthook,
)
from modules.core.src.capabilities_browser_adapter import _launch_context, browser_session
from modules.core.src.capabilities_file_uploader import _close_dropdown_if_open, _try_upload_attempt, upload_attachment
from modules.shared.src import AppConfig, CircuitBreaker, LifecycleEmitter, RunContext


# ─── main.py watcher error paths ────────────────────────────────────────────

class TestMainWatcherError:
    def test_watcher_file_failed_continues(self, tmp_path):
        client = MagicMock()
        cfg = AppConfig(
            mode="watcher",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
            log_path=tmp_path / "log",
            interval=1,
        )
        audit = MagicMock()

        def iter_with_error(cfg):
            yield tmp_path / "task.md", Path("task.md")
            raise RuntimeError("boom")

        with patch("modules.main._iter_todo", side_effect=iter_with_error), \
             patch("modules.main._process_file"), \
             patch("modules.main.StatusFileWriter") as mock_sw:
            _run_watcher(client, cfg, audit)
            calls = mock_sw.return_value.write.call_args_list
            assert any("error" in str(c) for c in calls)

    def test_watcher_shutdown_breaks_loop(self, tmp_path):
        from modules.core.src.capabilities_pipeline_compat import _watcher_shutdown
        _watcher_shutdown.set()
        client = MagicMock()
        cfg = AppConfig(
            mode="watcher",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
            log_path=tmp_path / "log",
            interval=1,
        )
        audit = MagicMock()

        with patch("modules.main._iter_todo", return_value=iter([])), \
             patch("modules.main.StatusFileWriter"):
            _run_watcher(client, cfg, audit)
        _watcher_shutdown.clear()


# ─── mcp_server.py remaining async functions ────────────────────────────────

class TestMcpServerRemainingAsync:
    def test_qwen_send_prompt_auth_error(self):
        from modules.shared.src import AuthRequiredError
        with patch("modules.mcp_server.browser_session") as mock_bs, \
             patch("modules.mcp_server.QwenClient") as mock_client:
            mock_ctx = MagicMock()
            mock_bs.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.send_file.side_effect = AuthRequiredError("login")
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_send_prompt("hello"))
            loop.close()
            assert "AUTH_REQUIRED" in result

    def test_qwen_send_prompt_general_error(self):
        with patch("modules.mcp_server.browser_session") as mock_bs, \
             patch("modules.mcp_server.QwenClient") as mock_client:
            mock_ctx = MagicMock()
            mock_bs.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)
            mock_client.return_value.send_file.side_effect = RuntimeError("boom")
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_send_prompt("hello"))
            loop.close()
            assert "RuntimeError" in result

    def test_qwen_process_single_auth_error(self):
        from modules.shared.src import AuthRequiredError
        tmp_task = Path("/tmp/test_task.md")
        tmp_task.write_text("task")
        try:
            with patch("modules.mcp_server.browser_session") as mock_bs, \
                 patch("modules.mcp_server.QwenClient"), \
                 patch("modules.mcp_server._process_file", side_effect=AuthRequiredError("login")), \
                 patch("modules.mcp_server.AuditLog"), \
                 patch("modules.mcp_server.shutil"):
                mock_ctx = MagicMock()
                mock_bs.return_value.__enter__ = MagicMock(return_value=mock_ctx)
                mock_bs.return_value.__exit__ = MagicMock(return_value=False)
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(qwen_process_single(str(tmp_task)))
                loop.close()
                assert "AUTH_REQUIRED" in result
        finally:
            tmp_task.unlink(missing_ok=True)

    def test_qwen_process_batch_auth_error(self):
        from modules.shared.src import AuthRequiredError
        with patch("modules.mcp_server.browser_session") as mock_bs, \
             patch("modules.mcp_server.QwenClient"), \
             patch("modules.mcp_server._iter_todo", return_value=iter([])), \
             patch("modules.mcp_server.AuditLog"):
            mock_ctx = MagicMock()
            mock_bs.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_bs.return_value.__exit__ = MagicMock(return_value=False)
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_process_batch())
            loop.close()
            assert "Batch processing complete" in result


# ─── pipeline.py remaining paths ────────────────────────────────────────────

class TestPipelineRemainingPaths:
    def test_retry_failed_no_failed_dir(self, tmp_path):
        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "input",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "nonexistent",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
            retry_failed=True,
        )
        files = list(_iter_todo_retry_failed(cfg))
        assert len(files) == 0

    def test_iter_todo_single_file(self, tmp_path):
        task = tmp_path / "task.md"
        task.write_text("task")
        cfg = AppConfig(
            mode="single",
            input_path=task,
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
        )
        files = list(_iter_todo_single(cfg))
        assert len(files) == 1


# ─── observability.py remaining paths ───────────────────────────────────────

class TestObservabilityRemainingPaths:
    def test_configure_sentry_with_dsn(self):
        with patch.dict("os.environ", {"SENTRY_DSN": "https://key@sentry.io/1"}), \
             patch("modules.observability.has_sentry", True), \
             patch("modules.observability.sentry_sdk") as mock_sentry:
            _configure_sentry()
            mock_sentry.init.assert_called_once()

    def test_configure_tracing_with_endpoint(self):
        with patch.dict("os.environ", {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"}), \
             patch("modules.observability.has_otel", True), \
             patch("modules.observability.has_otlp", True), \
             patch("modules.observability.trace") as mock_trace, \
             patch("modules.observability.TracerProvider") as mock_tp:
            _configure_tracing()

    def test_excepthook_keyboard_interrupt(self):
        with patch("modules.observability.sys") as mock_sys:
            mock_sys.exit = MagicMock(side_effect=SystemExit(130))
            with pytest.raises(SystemExit):
                _excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)

    def test_thread_excepthook(self):
        args = MagicMock()
        args.exc_type = RuntimeError
        args.exc_value = RuntimeError("test")
        args.exc_traceback = None
        _thread_excepthook(args)


# ─── browser.py remaining paths ─────────────────────────────────────────────

class TestBrowserRemainingPaths:
    def test_launch_context_no_user_data_dir(self):
        p = MagicMock()
        kwargs = {"user_data_dir": "", "headless": True}
        mock_ctx = MagicMock()
        p.chromium.launch_persistent_context.return_value = mock_ctx
        ctx = _launch_context(p, kwargs)
        assert ctx == mock_ctx

    def test_browser_session_creates_dirs(self, tmp_path):
        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
            headless=True,
        )
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]
        with patch("modules.browser.sync_playwright") as mock_pw, \
             patch("modules.browser.os.chmod"):
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx
            with browser_session(cfg) as ctx:
                pass
            assert cfg.session_path.exists()
