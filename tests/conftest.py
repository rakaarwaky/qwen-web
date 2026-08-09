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

_STATE_DIRS = ("done", "failed", ".processing")  # dirs that must be empty in clean state
_ROLES = list(_GOLDEN_TASKS.keys())
_LAST_RUN_FILE = FIXTURE_ROOT / ".last_run_ts"   # timestamp written by teardown
_OUTPUT_TTL_SECS = 60                              # keep output this long after test


def _restore_todo(fixture_root: Path) -> None:
    """Restore only todo/task_001.md for all roles. Does NOT touch output/ or log/.
    Used when output should be preserved for inspection.
    """
    fx_input = fixture_root / "input"
    for role in _ROLES:
        role_dir = fx_input / role
        # Clear state dirs (done/ failed/ .processing/) — these are never useful to inspect
        for state_dir in _STATE_DIRS:
            d = role_dir / state_dir
            d.mkdir(parents=True, exist_ok=True)
            for f in d.rglob("*"):
                if f.is_file():
                    f.unlink(missing_ok=True)
        # Restore the input task file
        todo_file = role_dir / "todo" / "task_001.md"
        todo_file.parent.mkdir(parents=True, exist_ok=True)
        todo_file.write_text(_GOLDEN_TASKS[role], encoding="utf-8")


def _full_reset(fixture_root: Path) -> None:
    """Full reset: restore todo files AND wipe output/ and log/.
    Called only when output TTL has expired or on explicit full reset.
    """
    _restore_todo(fixture_root)
    fx_output = fixture_root / "output"
    fx_log    = fixture_root / "log"
    for role in _ROLES:
        out_dir = fx_output / role
        out_dir.mkdir(parents=True, exist_ok=True)
        for f in out_dir.rglob("*"):
            if f.is_file():
                f.unlink(missing_ok=True)
    fx_log.mkdir(parents=True, exist_ok=True)
    for f in fx_log.rglob("*"):
        if f.is_file() and f.name != ".last_run_ts":
            f.unlink(missing_ok=True)


@pytest.fixture(autouse=False)
def reset_fixture_state(fixture_root: Path) -> None:  # type: ignore[return]
    """State manager for E2E tests. Output is cleaned under exactly 2 conditions:

      1. RERUN: a new test run starts and the previous output is >= 60s old.
      2. TIME:  60 seconds have elapsed since the last test completed.

    After the test finishes, output/ and log/ are kept intact for inspection.
    Only todo/task_001.md and state dirs (done/failed/.processing) are restored
    immediately so the next run can start cleanly.

    Golden state (always enforced on SETUP):
      input/<role>/todo/task_001.md   ← restored from golden content
      input/<role>/done/              ← empty
      input/<role>/failed/            ← empty
      input/<role>/.processing/       ← empty
      output/<role>/                  ← kept if <60s old, wiped if >=60s
      log/                            ← kept if <60s old, wiped if >=60s
    """
    import time as _time

    # ── SETUP: determine whether to do full reset or light restore ────────────
    last_run_ts: float = 0.0
    if _LAST_RUN_FILE.exists():
        try:
            last_run_ts = float(_LAST_RUN_FILE.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            last_run_ts = 0.0

    elapsed = _time.time() - last_run_ts
    if elapsed >= _OUTPUT_TTL_SECS:
        # Output is stale (>=60s) or this is the first run — full clean
        _full_reset(fixture_root)
        print(f"\n🧹 [FIXTURE RESET] Full reset (last run {elapsed:.0f}s ago)")
    else:
        # Output is fresh (<60s) — light restore: keep output/log, reset todo only
        _restore_todo(fixture_root)
        print(f"\n♻️  [FIXTURE RESET] Light restore (last run {elapsed:.0f}s ago — output preserved)")

    yield  # ── TEST RUNS ─────────────────────────────────────────────────────

    # ── TEARDOWN: record timestamp, restore todo, keep output for inspection ─
    _LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LAST_RUN_FILE.write_text(str(_time.time()), encoding="utf-8")
    _restore_todo(fixture_root)   # always restore input state
    # output/ and log/ are intentionally left intact for post-test inspection

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
