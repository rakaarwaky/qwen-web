"""Final push tests for remaining system integration code."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.core.src.capabilities_browser_adapter import BrowserAdapter, _assert_on_chat_page
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.core.src.capabilities_observability_setup import (
    ObservabilitySetup,
    _excepthook,
    _thread_excepthook,
)
from modules.root_cli_main_entry import main
from modules.root_mcp_main_entry import qwen_process_single, qwen_setup_session, qwen_start_watcher
from modules.shared.src.utility_core_path import (
    cleanup_empty_dirs,
    list_input_files,
    should_process_file,
)
from modules.shared.src import AppConfig, AuthRequiredError, LifecycleEmitter


# ─── browser.py coverage push ───────────────────────────────────────────────

class TestBrowserCoverage:
    def test_check_auth_no_tabs(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        page.query_selector.return_value = MagicMock()
        BrowserAdapter().check_auth(page)

    def test_navigate_to_chat_auth_check_fails(self):
        page = MagicMock()
        page.url = "https://chat.qwen.ai/"
        page.query_selector.return_value = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        with patch("modules.core.src.capabilities_browser_adapter._assert_on_chat_page", side_effect=AuthRequiredError("login")):
            with pytest.raises(AuthRequiredError):
                BrowserAdapter().navigate_to_chat(page, emitter)

    def test_assert_on_chat_page_auth_keywords(self):
        page = MagicMock()
        page.url = "https://accounts.google.com/signin"
        with pytest.raises(AuthRequiredError):
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
            with BrowserAdapter().browser_session(cfg) as ctx:
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
             patch("modules.core.src.capabilities_browser_adapter.os.chmod"):
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx
            with BrowserAdapter().browser_session(cfg) as ctx:
                pass

    def test_launch_context_with_user_data_dir(self):
        p = MagicMock()
        mock_ctx = MagicMock()
        p.chromium.launch_persistent_context.return_value = mock_ctx
        ctx = BrowserAdapter()._launch_context(p, {"user_data_dir": "/tmp/chrome", "headless": True})
        assert ctx == mock_ctx

    def test_launch_context_no_user_data_dir(self):
        p = MagicMock()
        mock_ctx = MagicMock()
        p.chromium.launch_persistent_context.return_value = mock_ctx
        ctx = BrowserAdapter()._launch_context(p, {"user_data_dir": "", "headless": True})
        assert ctx == mock_ctx


# ─── file_uploader.py coverage push ─────────────────────────────────────────

class TestFileUploaderCoverage:
    def test_close_dropdown_if_open_no_dropdown(self):
        page = MagicMock()
        FileUploader()._close_dropdown_if_open(page)
        page.keyboard.press.assert_called_once_with("Escape")

    def test_close_dropdown_if_open_keypress_error(self):
        page = MagicMock()
        page.keyboard.press.side_effect = Exception("page closed")
        FileUploader()._close_dropdown_if_open(page)

    def test_upload_attachment_no_file_input(self):
        page = MagicMock()
        page.locator.return_value.count.return_value = 0
        result = FileUploader().upload_attachment(page, Path("/tmp/test.md"))
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
        mock_slog = MagicMock()
        with patch.dict(sys.modules, {"structlog": mock_slog}):
            ObservabilitySetup(tmp_path / "log")._configure_logging(tmp_path / "log")
            mock_slog.configure.assert_called()

    def test_configure_sentry_no_dsn(self, tmp_path):
        mock_sentry = MagicMock()
        with patch.dict("os.environ", {}, clear=False), \
             patch.dict(sys.modules, {"sentry_sdk": mock_sentry}):
            os.environ.pop("SENTRY_DSN", None)
            ObservabilitySetup(tmp_path / "log")._configure_sentry()
            mock_sentry.init.assert_not_called()

    def test_configure_tracing_no_endpoint(self, tmp_path):
        mock_otel = MagicMock()
        mock_sdk_resources = MagicMock()
        mock_sdk_trace = MagicMock()
        mock_sdk_trace_export = MagicMock()
        mock_otlp_exporter = MagicMock()
        otel_modules = {
            "opentelemetry": mock_otel,
            "opentelemetry.sdk": MagicMock(),
            "opentelemetry.sdk.resources": mock_sdk_resources,
            "opentelemetry.sdk.trace": mock_sdk_trace,
            "opentelemetry.sdk.trace.export": mock_sdk_trace_export,
            "opentelemetry.exporter": MagicMock(),
            "opentelemetry.exporter.otlp": MagicMock(),
            "opentelemetry.exporter.otlp.proto": MagicMock(),
            "opentelemetry.exporter.otlp.proto.http": MagicMock(),
            "opentelemetry.exporter.otlp.proto.http.trace_exporter": mock_otlp_exporter,
        }
        with patch.dict("os.environ", {}, clear=False), \
             patch.dict(sys.modules, otel_modules):
            os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
            ObservabilitySetup(tmp_path / "log")._configure_tracing()
            mock_otel.trace.set_tracer_provider.assert_called()

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
        with patch.object(ObservabilitySetup, "_configure_logging"), \
             patch.object(ObservabilitySetup, "_configure_sentry"), \
             patch.object(ObservabilitySetup, "_configure_tracing"), \
             patch("modules.core.src.capabilities_observability_setup.os.environ", {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://x:4318"}):
            ObservabilitySetup(tmp_path / "log").setup_observability()


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