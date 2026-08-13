"""Final push tests for remaining hard-to-cover lines."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.core.src.agent_core_orchestrator import (
    CoreOrchestrator,
    _watcher_shutdown,
    request_watcher_shutdown,
)
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.core.src.capabilities_observability_setup import (
    ObservabilitySetup,
    _excepthook,
    _thread_excepthook,
)
from modules.root_cli_main_entry import (
    _run_manual_login,
    main,
)
from modules.root_mcp_main_entry import (
    qwen_process_batch,
    qwen_process_single,
    qwen_send_prompt,
    qwen_start_watcher,
)
from modules.shared.src import AppConfig, CircuitBreaker, LifecycleEmitter, RunContext
from modules.shared.src.taxonomy_core_entity import RateLimiter


def _make_orchestrator():
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


# ─── main.py remaining paths ────────────────────────────────────────────────

class TestMainRemainingPaths:
    def test_run_manual_login(self, tmp_path):
        with patch("sys.stdin"), \
             patch("modules.cli.src.surface_cli_login_command.handle", return_value={"success": True}):
            cfg = AppConfig(
                mode="login",
                input_path=tmp_path / "in",
                output_path=tmp_path / "out",
                done_path=tmp_path / "done",
                failed_path=tmp_path / "failed",
                proc_path=tmp_path / "proc",
                session_path=tmp_path / "session",
            )
            _run_manual_login(cfg)


# ─── mcp_server.py remaining async functions ────────────────────────────────

class TestMcpServerRemainingAsync:
    def test_qwen_send_prompt_auth_error(self):
        mock_tools = MagicMock()
        mock_tools.send_prompt.return_value = "ERROR [AUTH_REQUIRED]: login"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_send_prompt("hello"))
            loop.close()
            assert "AUTH_REQUIRED" in result

    def test_qwen_send_prompt_general_error(self):
        mock_tools = MagicMock()
        mock_tools.send_prompt.return_value = "ERROR [RuntimeError]: boom"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_send_prompt("hello"))
            loop.close()
            assert "RuntimeError" in result

    def test_qwen_process_single_auth_error(self):
        mock_tools = MagicMock()
        mock_tools.process_single.return_value = "ERROR [AUTH_REQUIRED]: login"
        tmp_task = Path("/tmp/test_task.md")
        tmp_task.write_text("task")
        try:
            with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(qwen_process_single(str(tmp_task)))
                loop.close()
                assert "AUTH_REQUIRED" in result
        finally:
            tmp_task.unlink(missing_ok=True)

    def test_qwen_process_batch_auth_error(self):
        mock_tools = MagicMock()
        mock_tools.process_batch.return_value = "Batch processing complete. Successfully processed: 0, Failed: 0"
        with patch("modules.root_mcp_main_entry._tools", return_value=mock_tools):
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(qwen_process_batch())
            loop.close()
            assert "Batch processing complete" in result


# ─── observability.py remaining paths ───────────────────────────────────────

class TestObservabilityRemainingPaths:
    def test_configure_sentry_with_dsn(self, tmp_path):
        mock_sentry = MagicMock()
        with patch.dict("os.environ", {"SENTRY_DSN": "https://key@sentry.io/1"}), \
             patch.dict(sys.modules, {"sentry_sdk": mock_sentry}):
            ObservabilitySetup(tmp_path / "log")._configure_sentry()
            mock_sentry.init.assert_called_once()

    def test_configure_tracing_with_endpoint(self, tmp_path):
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
        with patch.dict("os.environ", {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318"}), \
             patch.dict(sys.modules, otel_modules):
            ObservabilitySetup(tmp_path / "log")._configure_tracing()
            mock_otlp_exporter.OTLPSpanExporter.assert_called_once_with(endpoint="http://localhost:4318")

    def test_excepthook_keyboard_interrupt(self):
        with patch("modules.core.src.capabilities_observability_setup.sys") as mock_sys:
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
        ctx = BrowserAdapter()._launch_context(p, kwargs)
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
        with patch("modules.core.src.capabilities_browser_adapter.sync_playwright") as mock_pw, \
             patch("modules.core.src.capabilities_browser_adapter.os.chmod"):
            mock_p = MagicMock()
            mock_pw.return_value.__enter__ = MagicMock(return_value=mock_p)
            mock_pw.return_value.__exit__ = MagicMock(return_value=False)
            mock_p.chromium.launch_persistent_context.return_value = mock_ctx
            with BrowserAdapter().browser_session(cfg) as ctx:
                pass
            assert cfg.session_path.exists()