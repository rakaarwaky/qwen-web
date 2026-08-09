"""Shared pytest fixtures for the QwenClient behavior-lock regression suite.

Two fixture layers:

1. BROWSER fixtures (browser_ctx, page, client):
   Spin up a REAL headless Chromium against a local HTML fixture that mirrors
   the exact DOM structure of chat.qwen.ai. Every page.evaluate() / locator
   call in src/qwen_client.py executes against real DOM + real JS.

2. PIPELINE fixtures (fixture_root, cfg, audit, run_ctx):
   Wire tests/fixtures/ as a 1:1 isolated mirror of the production runtime
   directory structure (input/, output/, log/). All fixtures use the real
   AppConfig, AuditLog, and RunContext constructors from src/ — no invented
   business logic. Log output is redirected to pytest tmp_path so each test
   run is isolated and tests/fixtures/log/ is never mutated.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from playwright.sync_api import BrowserContext, sync_playwright

# make src importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from config import AppConfig  # noqa: E402
from pipeline import AuditLog, _list_input_files, resolve_role_paths, load_role_prompt  # noqa: E402
from qwen_client import QwenClient  # noqa: E402
from config import RunContext  # noqa: E402

FIXTURE = (Path(__file__).resolve().parent / "fixtures" / "qwen_fixture.html").as_uri()


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
        mode="batch", input_path=ROOT / "input", output_path=ROOT / "output",
        done_path=ROOT / "input" / "done", failed_path=ROOT / "input" / "failed",
        proc_path=ROOT / "input" / ".processing", session_path=ROOT / "qwen_session",
        headless=True,
    )
    c = QwenClient(browser_ctx, headless=True)
    # ensure the client uses our fixture page, not a fresh one
    c._page = page
    return c


# ─── Pipeline / filesystem fixtures ─────────────────────────────────────────
# These are 1:1 mirrors of what production main.py builds. Every path,
# every constructor call is identical to the real runtime — only the
# root directory is redirected to tests/fixtures/.

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def fixture_root() -> Path:
    """Absolute path to tests/fixtures/ — single source of truth for all paths."""
    return FIXTURE_ROOT


@pytest.fixture
def cfg(fixture_root: Path, tmp_path: Path) -> AppConfig:
    """Real AppConfig wired to tests/fixtures/ input & output, log redirected
    to tmp_path so each test run is isolated (no log pollution in fixtures/).
    Uses the identical AppConfig constructor as production main.py.
    """
    fx_input  = fixture_root / "input"
    fx_output = fixture_root / "output"
    return AppConfig(
        mode="batch",
        input_path=fx_input,
        output_path=fx_output,
        done_path=fx_input / "role-architect" / "done",   # overridden per-role by resolve_role_paths
        failed_path=fx_input / "role-architect" / "failed",
        proc_path=fx_input / "role-architect" / ".processing",
        session_path=fixture_root / "qwen_session",
        log_path=tmp_path / "log",   # isolated per test run
        headless=True,
    )


@pytest.fixture
def audit(cfg: AppConfig) -> AuditLog:
    """Real AuditLog(cfg.log_path) — same constructor call as production main.py."""
    return AuditLog(cfg.log_path)


@pytest.fixture
def run_ctx() -> RunContext:
    """Real RunContext() — same factory as production main.py."""
    return RunContext()
