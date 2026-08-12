"""Final push tests for remaining system integration code."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.core.src.capabilities_browser_adapter import (
    _assert_on_chat_page,
    check_auth,
    _clean_stale_locks,
    _launch_context,
    browser_session,
    navigate_to_chat,
)
from modules.core.src.capabilities_file_uploader import (
    _close_dropdown_if_open,
    _try_upload_attempt,
    upload_attachment,
)
from modules.root_cli_main_entry import main
from modules.root_mcp_main_entry import qwen_process_single, qwen_setup_session, qwen_start_watcher
from modules.core.src.capabilities_observability_setup import (
    _configure_logging,
    _configure_sentry,
    _configure_tracing,
    _excepthook,
    _thread_excepthook,
    setup_observability,
)
from modules.shared.src.utility_core_path import (
    cleanup_empty_dirs,
    list_input_files,
    should_process_file,
)
from modules.shared.src import AppConfig, LifecycleEmitter


# ─── browser.py coverage push ───────────────────────────────────────────────

class TestBrowserCoverage:
    def test_check_auth_no_tabs(self):
        browser = MagicMock()
        browser.contexts = [MagicMock(pages=[])]
        check_auth(browser)

    def test_navigate_to_chat_auth_check_fails(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        # Make assert_on_chat_page happy: URL is fine, textarea exists
        page.query_selector.return_value = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        with patch("modules.core.src.capabilities_browser_adapter.check_auth", side_effect=Exception("login")):
            navigate_to_chat(page, emitter)

    def test_assert_on_chat_page_auth_keywords(self):
        page = MagicMock()
        page.url = "https://accounts.google.com/signin"
        with pytest.raises(Exception):
            _assert_on_chat_page(page)

    def test_browser_session_headless(self, tmp_path):
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
        with patch("modules.core.src.capabilities_browser_adapter.sync_playwright") as mock_pw, \
             patch("modules.core.src.capabilities_browser_adapter.os.chmod"):
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx
            with browser_session(cfg) as ctx:
                pass

    def test_browser_session_headed(self, tmp_path):
        cfg = AppConfig(
            mode="batch",
            input_path=tmp_path / "in",
            output_path=tmp_path / "out",
            done_path=tmp_path / "done",
            failed_path=tmp_path / "failed",
            proc_path=tmp_path / "proc",
            session_path=tmp_path / "session",
            headless=False,
        )
        mock_ctx = MagicMock()
        mock_ctx.pages = [MagicMock()]
        with patch("modules.core.src.capabilities_browser_adapter.sync_playwright") as mock_pw, \
             patch("modules.core.src.capabilities_browser_adapter.os.chmod"), \
             patch("modules.core.src.capabilities_browser_adapter.os.makedirs"):
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx
            with browser_session(cfg) as ctx:
                pass

    def test_launch_context_with_user_data_dir(self):
        p = MagicMock()
        mock_ctx = MagicMock()
        p.chromium.launch_persistent_context.return_value = mock_ctx
        with patch("modules.core.src.capabilities_browser_adapter.os.makedirs"), \
             patch("modules.core.src.capabilities_browser_adapter.os.chmod"), \
             patch("modules.core.src.capabilities_browser_adapter.Path.mkdir"):
            ctx = _launch_context(p, {"user_data_dir": "/tmp/chrome", "headless": True})
            assert ctx == mock_ctx

    def test_launch_context_no_user_data_dir(self):
        p = MagicMock()
        mock_ctx = MagicMock()
        p.chromium.launch_persistent_context.return_value = mock_ctx
        ctx = _launch_context(p, {"user_data_dir": "", "headless": True})
        assert ctx == mock_ctx


# ─── file_uploader.py coverage push ─────────────────────────────────────────

class TestFileUploaderCoverage:
    def test_close_dropdown_if_open_no_dropdown(self):
        page = MagicMock()
        page.query_selector.return_value = None
        _close_dropdown_if_open(page)

    def test_close_dropdown_if_open_hidden_dropdown(self):
        page = MagicMock()
        dropdown = MagicMock()
        dropdown.is_visible.return_value = False
        page.query_selector.return_value = dropdown
        _close_dropdown_if_open(page)

    def test_upload_attachment_no_file_input(self):
        page = MagicMock()
        page.locator.return_value.count.return_value = 0
        result = upload_attachment(page, Path("/tmp/test.md"))
        assert result is False


# ─── mcp_server.py remaining async ──────────────────────────────────────────

class TestMcpServerRemainingAsync:
    def test_qwen_process_single_error(self):
        mock_tools = MagicMock()
        mock_tools.process_single.return_value = "ERROR [RuntimeError]: boom"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            tmp = Path("/tmp/err_task.md")
            tmp.write_text("x")
            try:
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(qwen_process_single(str(tmp)))
                loop.close()
                assert "RuntimeError" in result
            finally:
                tmp.unlink(missing_ok=True)

    def test_qwen_start_watcher(self):
        mock_tools = MagicMock()
        mock_tools.start_watcher.return_value = "Watcher loop completed."
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_start_watcher(interval_sec=1))
            loop.close()
            assert "Watcher loop completed" in result


# ─── observability.py remaining paths ───────────────────────────────────────

class TestObservabilityCoverage:
    def test_configure_logging_structlog(self, tmp_path):
        with patch("modules.core.src.capabilities_observability_setup.has_structlog", True), \
             patch("modules.core.src.capabilities_observability_setup.structlog") as mock_slog:
            _configure_logging(tmp_path / "log")
            mock_slog.configure.assert_called()

    def test_configure_sentry_no_dsn(self):
        with patch.dict("os.environ", {}, clear=False), \
             patch("modules.core.src.capabilities_observability_setup.has_sentry", True), \
             patch("modules.core.src.capabilities_observability_setup.sentry_sdk") as mock_sentry:
            os.environ.pop("SENTRY_DSN", None)
            _configure_sentry()

    def test_configure_tracing_no_endpoint(self):
        with patch.dict("os.environ", {}, clear=False), \
             patch("modules.core.src.capabilities_observability_setup.has_otel", True):
            os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            _configure_tracing()

    def test_thread_excepthook_real(self):
        args = MagicMock()
        args.exc_type = RuntimeError
        args.exc_value = RuntimeError("boom")
        args.exc_traceback = None
        _thread_excepthook(args)

    def test_excepthook_non_keyboard(self):
        with patch("modules.core.src.capabilities_observability_setup.sys") as mock_sys:
            mock_sys.exit = MagicMock()
            _excepthook(RuntimeError, RuntimeError("boom"), None)

    def test_setup_observability_with_tracing(self, tmp_path):
        with patch("modules.core.src.capabilities_observability_setup._configure_logging"), \
             patch("modules.core.src.capabilities_observability_setup._configure_sentry"), \
             patch("modules.core.src.capabilities_observability_setup._configure_tracing"), \
             patch("modules.core.src.capabilities_observability_setup.has_otel", True), \
             patch("modules.core.src.capabilities_observability_setup.os.environ", {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://x:4318"}):
            setup_observability(tmp_path / "log")


# ─── pipeline.py remaining paths ────────────────────────────────────────────

class TestPipelineCoverage:
    def test_list_input_files_ignores_hidden(self, tmp_path):
        f = tmp_path / ".hidden"
        f.mkdir()
        files = list_input_files(tmp_path)
        assert len(files) == 0

    def test_should_process_file_in_output_dir(self, tmp_path):
        f = tmp_path / "output" / "task.md"
        f.parent.mkdir(parents=True)
        f.write_text("x")
        assert should_process_file(f, tmp_path) is False

    def test_should_process_file_in_proc_dir(self, tmp_path):
        f = tmp_path / "proc" / "task.md"
        f.parent.mkdir(parents=True)
        f.write_text("x")
        assert should_process_file(f, tmp_path) is False

    def test_cleanup_empty_dirs_preserves_nonempty(self, tmp_path):
        d = tmp_path / "keep"
        d.mkdir()
        (d / "file.md").write_text("x")
        cleanup_empty_dirs(d, tmp_path)
        assert d.exists()
