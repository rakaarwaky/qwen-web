"""Unit tests for centralized types, error categorizers, exit code mapping, and configuration models."""

from __future__ import annotations

from pathlib import Path

from modules.core.src.capabilities_observability_setup import exit_code_for
from modules.shared.src import (
    AuthRequiredError,
    BrowserConfig,
    ErrorCategory,
    InjectorConfig,
    MCPServerConfig,
    MCPToolResponse,
    RunContext,
    SenderConfig,
    StatusRecord,
    StreamerConfig,
    UploadConfig,
)


def test_error_category_classification():
    assert ErrorCategory.categorize(AuthRequiredError("login required")) == "auth"
    assert ErrorCategory.categorize(TimeoutError("connection dropped")) == "network"
    assert ErrorCategory.categorize(RuntimeError("429 rate limit exceeded")) == "rate_limit"
    assert ErrorCategory.categorize(RuntimeError("chromium page crashed")) == "browser"
    assert ErrorCategory.categorize(RuntimeError("prompt fill failed")) == "injection"
    assert ErrorCategory.categorize(ValueError("parse empty response")) == "parsing"
    assert ErrorCategory.categorize(OSError("disk I/O error")) == "file_io"
    assert ErrorCategory.categorize(Exception("unhandled custom error")) == "other"


def test_exit_code_for_mapping():
    assert exit_code_for(KeyboardInterrupt()) == 130
    assert exit_code_for(AuthRequiredError("login")) == 2
    assert exit_code_for(RuntimeError("general error")) == 1


def test_run_context_uniqueness():
    ctx1 = RunContext()
    ctx2 = RunContext()
    assert ctx1.run_id != ctx2.run_id


def test_config_defaults(tmp_path: Path):
    upload_cfg = UploadConfig()
    assert upload_cfg.max_file_size_mb == 100.0

    inj_cfg = InjectorConfig()
    assert inj_cfg.wait_timeout_ms == 10_000

    browser_cfg = BrowserConfig()
    assert browser_cfg.headless is True

    sender_cfg = SenderConfig()
    assert sender_cfg.click_timeout_ms == 3000

    streamer_cfg = StreamerConfig()
    assert streamer_cfg.stability_checks == 3

    mcp_cfg = MCPServerConfig()
    assert mcp_cfg.server_name == "Qwen-Web"

    mcp_resp = MCPToolResponse(success=True, data="ok")
    assert mcp_resp.success is True

    status_rec = StatusRecord(status="RUNNING", mode="single", headless=True)
    assert status_rec.status == "RUNNING"
