"""Shared pytest fixtures for the QwenClient behavior-lock regression suite.

Fixtures layered cleanly across:
1. Browser Layer (browser_ctx, page, client)
2. Pipeline Layer (fixture_root, cfg, audit, run_ctx)
3. E2E Layer (e2e_cfg)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from playwright.sync_api import BrowserContext, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipeline import AuditLog, load_role_prompt, resolve_role_paths  # noqa: E402
from src.qwen_client import QwenClient  # noqa: E402
from src.types import AppConfig, RunContext  # noqa: E402
from tests.pipeline_fixtures import restore_fixture_state  # noqa: E402

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
FIXTURE = (FIXTURE_ROOT / "qwen_fixture.html").as_uri()


@pytest.fixture(scope="session")
def browser_ctx() -> BrowserContext:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir="",  # ephemeral
            headless=True,
            permissions=["clipboard-read", "clipboard-write"],
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            viewport={"width": 1280, "height": 800},
        )
        yield ctx
        try:
            ctx.close()
        except Exception:
            pass


@pytest.fixture(autouse=True, scope="session")
def _reset_event_loop_at_session_end():
    """Reset asyncio event loop after session to prevent cross-module contamination."""
    yield
    import asyncio
    try:
        if hasattr(asyncio, "_set_running_loop"):
            asyncio._set_running_loop(None)
    except Exception:
        pass
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception:
        pass


@pytest.fixture
def page(browser_ctx: BrowserContext):
    pg = browser_ctx.new_page()
    pg.goto(FIXTURE, wait_until="domcontentloaded")
    pg.wait_for_timeout(200)
    yield pg
    try:
        pg.close()
    except Exception:
        pass


@pytest.fixture
def client(browser_ctx: BrowserContext, page) -> QwenClient:
    cfg = AppConfig(
        mode="batch",
        input_path=ROOT / "input",
        output_path=ROOT / "output",
        done_path=ROOT / "input" / "done",
        failed_path=ROOT / "input" / "failed",
        proc_path=ROOT / "input" / ".processing",
        session_path=ROOT / "qwen_session",
        headless=True,
    )
    c = QwenClient(browser_ctx, cfg)
    c.page = page
    return c


@pytest.fixture(scope="session")
def fixture_root() -> Path:
    """Absolute path to tests/fixtures/ — single source of truth for all paths."""
    return FIXTURE_ROOT


@pytest.fixture
def cfg(fixture_root: Path, tmp_path: Path, reset_fixture_state) -> AppConfig:
    fx_input = fixture_root / "input"
    fx_output = fixture_root / "output"
    return AppConfig(
        mode="batch",
        input_path=fx_input,
        output_path=fx_output,
        done_path=fx_input / "role-architect" / "done",
        failed_path=fx_input / "role-architect" / "failed",
        proc_path=fx_input / "role-architect" / ".processing",
        session_path=fixture_root / "qwen_session",
        log_path=tmp_path / "log",
        headless=True,
    )


@pytest.fixture
def audit(cfg: AppConfig) -> AuditLog:
    return AuditLog(cfg.log_path)


@pytest.fixture
def run_ctx() -> RunContext:
    return RunContext()


@pytest.fixture(autouse=True)
def reset_fixture_state(fixture_root: Path):
    restore_fixture_state(fixture_root)
    yield
    restore_fixture_state(fixture_root)


@pytest.fixture
def e2e_cfg(fixture_root: Path, reset_fixture_state) -> AppConfig:
    fx_input = fixture_root / "input"
    fx_output = fixture_root / "output"
    target_file = fx_input / "role-architect" / "todo" / "task_001.md"
    return AppConfig(
        mode="single",
        input_path=target_file if target_file.exists() else fx_input,
        output_path=fx_output,
        done_path=fx_input / "role-architect" / "done",
        failed_path=fx_input / "role-architect" / "failed",
        proc_path=fx_input / "role-architect" / ".processing",
        session_path=fixture_root / "qwen_session",
        log_path=fixture_root / "log",
        headless=True,
        timeout=300,
    )
