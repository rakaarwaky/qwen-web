"""Shared pytest fixtures for the QwenClient behavior-lock regression suite.

Three fixture layers:

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

3. E2E fixtures (e2e_cfg):
   Wire tests/fixtures/ input/output/log WITH the real qwen_session so the
   full pipeline (browser_session → QwenClient → _process_file) runs against
   live chat.qwen.ai. Requires internet + valid saved session. Tests that use
   this fixture are marked @pytest.mark.e2e and excluded from normal CI runs.
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


# ─── E2E fixtures ─────────────────────────────────────────────────────────────
# Layer 3: full pipeline against live chat.qwen.ai, paths redirected to
# tests/fixtures/ so the real input/ output/ log/ dirs are never touched.
# Requires internet + a valid saved session in qwen_session/.

# ── Golden state: exact content of each todo/task_001.md ─────────────────────
# Stored here so reset_fixture_state can always recreate them, even after
# a crash, interrupt, or repeated test run.
_GOLDEN_TASKS: dict[str, str] = {
    "role-architect": """\
# Review Request: auth module architecture

Please review the `modules/auth/` directory and identify any layer boundary
violations, naming issues, or orphaned files.

Focus on:
- Import direction compliance
- SRP adherence
- Testability of each component
""",
    "role-business-analyst": """\
# User Story Gap Analysis: Payment Feature

Analyze the acceptance criteria for the `payment` feature user stories.

Identify:
- Missing edge cases
- Ambiguous acceptance criteria
- Stories without testable outcomes
""",
    "role-tech-lead": """\
# PR Review: LRU Cache Implementation

Review the implementation in `modules/cache/lru.py`.

Check:
- Code quality and naming conventions
- Test coverage adequacy
- Performance implications of the eviction policy
- Thread safety concerns

Provide a go/no-go recommendation.
""",
}

_ROLES = list(_GOLDEN_TASKS.keys())
_STATE_DIRS = ("done", "failed", ".processing")  # dirs that must be empty in clean state


def _reset_to_golden(fixture_root: Path) -> None:
    """Reset tests/fixtures/ to its clean initial state:
    - todo/task_001.md   → recreated from golden content
    - done/ failed/ .processing/ → emptied
    - output/<role>/     → emptied
    - log/               → emptied

    Safe to call at any time: before test, after test, after crash/interrupt.
    """
    fx_input  = fixture_root / "input"
    fx_output = fixture_root / "output"
    fx_log    = fixture_root / "log"

    for role in _ROLES:
        role_dir = fx_input / role

        # 1. Empty state dirs (done/, failed/, .processing/)
        for state_dir in _STATE_DIRS:
            d = role_dir / state_dir
            d.mkdir(parents=True, exist_ok=True)
            for f in d.rglob("*"):
                if f.is_file():
                    f.unlink(missing_ok=True)

        # 2. Restore todo/task_001.md from golden content
        todo_file = role_dir / "todo" / "task_001.md"
        todo_file.parent.mkdir(parents=True, exist_ok=True)
        todo_file.write_text(_GOLDEN_TASKS[role], encoding="utf-8")

        # 3. Empty output/<role>/
        out_dir = fx_output / role
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in out_dir.rglob("*"):
            if f.is_file():
                f.unlink(missing_ok=True)

    # 4. Empty log/ (keep the dir, wipe the files)
    fx_log.mkdir(parents=True, exist_ok=True)
    for f in fx_log.rglob("*"):
        if f.is_file():
            f.unlink(missing_ok=True)


@pytest.fixture(autouse=False)
def reset_fixture_state(fixture_root: Path) -> None:  # type: ignore[return]
    """Autouse fixture for E2E tests that ensures tests/fixtures/ is in its
    golden state BEFORE the test and AFTER the test (teardown always runs,
    even on crash or KeyboardInterrupt).

    Golden state:
      input/<role>/todo/task_001.md   ← exists, original content
      input/<role>/done/              ← empty
      input/<role>/failed/            ← empty
      input/<role>/.processing/       ← empty
      output/<role>/                  ← empty
      log/                            ← empty

    Use explicitly in E2E tests:
        def test_foo(self, reset_fixture_state, ...):
    """
    _reset_to_golden(fixture_root)   # ── SETUP: clean slate before test
    yield
    _reset_to_golden(fixture_root)   # ── TEARDOWN: restore after test


@pytest.fixture
def e2e_cfg(fixture_root: Path) -> AppConfig:
    """Real AppConfig for E2E tests.

    Identical constructor to production main.py — only paths redirected to
    tests/fixtures/. Uses the real qwen_session/ for authentication.
    log_path points to tests/fixtures/log/ (persistent — inspect after run).
    """
    fx_input  = fixture_root / "input"
    fx_output = fixture_root / "output"
    return AppConfig(
        mode="batch",
        input_path=fx_input,
        output_path=fx_output,
        done_path=fx_input / "role-architect" / "done",
        failed_path=fx_input / "role-architect" / "failed",
        proc_path=fx_input / "role-architect" / ".processing",
        session_path=ROOT / "qwen_session",   # real saved session
        log_path=fixture_root / "log",         # persistent — inspect after run
        headless=True,
    )


@pytest.fixture
def e2e_cfg(fixture_root: Path) -> AppConfig:
    """Real AppConfig for E2E tests.

    Identical constructor to production main.py — only paths redirected to
    tests/fixtures/. Uses the real qwen_session/ for authentication.
    log_path points to tests/fixtures/log/ (persistent — inspect after run).
    """
    fx_input  = fixture_root / "input"
    fx_output = fixture_root / "output"
    return AppConfig(
        mode="batch",
        input_path=fx_input,
        output_path=fx_output,
        done_path=fx_input / "role-architect" / "done",
        failed_path=fx_input / "role-architect" / "failed",
        proc_path=fx_input / "role-architect" / ".processing",
        session_path=ROOT / "qwen_session",   # real saved session
        log_path=fixture_root / "log",         # persistent — inspect after run
        headless=True,
    )
