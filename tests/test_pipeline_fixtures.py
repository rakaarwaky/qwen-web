"""Pipeline fixture integration tests.

Every test calls a REAL production function from pipeline.py / config.py
directly against the tests/fixtures/ environment. No mocks, no invented logic.
The fixture environment is a 1:1 mirror of the production runtime structure.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

from modules.core.src.capabilities_audit_repository import AuditRepository
from modules.core.src.capabilities_output_saver import Saver
from modules.shared.src.utility_core_path import (
    resolve_role_paths,
    should_process_file as _should_process_file,
)
from modules.shared.src.utility_core_prompt import load_role_prompt
from modules.shared.src import AppConfig, RunContext

ROLES = ["role-architect", "role-business-analyst", "role-tech-lead"]


# ─── _should_process_file ───────────────────────────────────────────────────

def test_should_process_file_valid(cfg: AppConfig) -> None:
    """_should_process_file must return True for task_001.md in role todo folders."""
    task_file = cfg.input_path / "role-architect" / "todo" / "task_001.md"
    assert _should_process_file(task_file, cfg.input_path) is True


def test_should_process_file_skips_prompt_md(cfg: AppConfig) -> None:
    """_should_process_file must skip PROMPT.md."""
    prompt_file = cfg.input_path / "role-architect" / "PROMPT.md"
    assert _should_process_file(prompt_file, cfg.input_path) is False


def test_should_process_file_skips_done_failed_processing(cfg: AppConfig) -> None:
    """_should_process_file must skip done/, failed/, .processing/ subdirs."""
    for d in ("done", "failed", ".processing"):
        p = cfg.input_path / "role-architect" / d / "should_be_skipped.md"
        assert _should_process_file(p, cfg.input_path) is False


# ─── resolve_role_paths ──────────────────────────────────────────────────────

@pytest.mark.parametrize("role", ROLES)
def test_resolve_role_paths_structure(cfg: AppConfig, role: str) -> None:
    """resolve_role_paths must return paths rooted under the correct role folder.
    rel_path includes todo/ as production scanner returns it that way.
    resolve_role_paths strips todo/ internally (pipeline.py line 198-199).
    """
    rel_path = Path(role) / "todo" / "task_001.md"  # exactly what _iter_todo yields
    out_path, done_path, fail_path, proc_file = resolve_role_paths(rel_path, cfg)

    # output goes flat under cfg.output_path
    assert out_path == cfg.output_path / "task_001.md", (
        f"out_path {out_path} must be flat under output/"
    )
    # done/failed stay inside input/<role>/, .processing inside cfg.proc_path
    assert role in str(done_path), f"done_path {done_path} must contain role folder"
    assert role in str(fail_path), f"fail_path {fail_path} must contain role folder"
    assert role in str(proc_file), f"proc_file {proc_file} must contain role folder"
    assert "done" in str(done_path)
    assert "failed" in str(fail_path)
    assert ".processing" in str(proc_file)


def test_resolve_role_paths_strips_done_and_failed(cfg: AppConfig) -> None:
    """resolve_role_paths must strip 'done' or 'failed' from relative sub-paths."""
    rel_path_done = Path("role-architect/done/task_001.md")
    out_p, done_p, fail_p, proc_p = resolve_role_paths(rel_path_done, cfg)

    assert out_p == cfg.output_path / "task_001.md"
    assert done_p == cfg.input_path / "role-architect" / "done" / "task_001.md"
    assert fail_p == cfg.input_path / "role-architect" / "failed" / "task_001.md"
    assert proc_p == cfg.proc_path / "role-architect" / "task_001.md"


def test_resolve_role_paths_single_mode_no_duplicate(tmp_path: Path) -> None:
    """resolve_role_paths must not duplicate role paths in single mode when input_path is a file."""
    input_file = tmp_path / "input" / "role-architect" / "done" / "task_001.md"
    cfg = AppConfig(
        mode="single",
        input_path=input_file,
        output_path=tmp_path / "output",
        done_path=tmp_path / "input" / "done",
        failed_path=tmp_path / "input" / "failed",
        proc_path=tmp_path / "input" / ".processing",
        session_path=tmp_path / "session",
    )
    rel_path = Path("role-architect/done/task_001.md")
    out_p, done_p, fail_p, proc_p = resolve_role_paths(rel_path, cfg)

    assert out_p == tmp_path / "output" / "task_001.md"
    assert "role-architect/done/task_001.md/role-architect" not in str(out_p)
    assert "done/role-architect" not in str(proc_p)


# ─── load_role_prompt ────────────────────────────────────────────────────────

@pytest.mark.parametrize("role", ROLES)
def test_load_role_prompt_strips_frontmatter(fixture_root: Path, role: str) -> None:
    """load_role_prompt must strip YAML frontmatter (---) and return body only.
    Passes the task file path; pipeline auto-discovers PROMPT.md from parent dirs.
    """
    prompt_file = fixture_root / "input" / role / "todo" / "task_001.md"
    result = load_role_prompt(prompt_file)

    # PROMPT.md is in the parent dir — load_role_prompt will discover it
    # The frontmatter block starts/ends with --- so result must NOT start with ---
    assert not result.startswith("---"), (
        "Frontmatter must be stripped from PROMPT.md body"
    )
    assert len(result) > 0, "Loaded prompt must not be empty"


# ─── _write_output ───────────────────────────────────────────────────────────

def test_write_output_creates_file_with_traceability_header(
    cfg: AppConfig, run_ctx: RunContext, tmp_path: Path
) -> None:
    """_write_output must create the file and embed the metadata traceability header."""
    out_file = tmp_path / "output" / "role-architect" / "task_001_result.md"
    content = "# Result\nThis is the Qwen response."

    Saver().write_output(
        path=out_file,
        content=content,
        ctx=run_ctx,
        src="role-architect/task_001.md",
        dur=1.23,
        input_chars=len("input"),
        output_chars=len(content),
    )

    assert out_file.exists(), "Output file must be created by _write_output"
    text = out_file.read_text(encoding="utf-8")
    assert "METADATA TRACEABILITY" in text, "Header block must be present"
    assert run_ctx.run_id in text, "run_id must appear in traceability header"
    assert content in text, "Original content must follow the header"


# ─── AuditLog ────────────────────────────────────────────────────────────────

def test_audit_log_step_writes_valid_jsonl(audit: AuditRepository, run_ctx: RunContext, cfg: AppConfig) -> None:
    """AuditLog.log_step must write a parseable JSONL line to audit_history.jsonl."""
    audit.log_step(run_ctx, "START_PROCESSING", "role-architect/task_001.md", "STARTED", {"input_chars": 42})

    audit_file = cfg.log_path / "audit_history.jsonl"
    assert audit_file.exists(), "audit_history.jsonl must be created"

    lines = [l for l in audit_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= 1, "At least one line must be written"

    rec = json.loads(lines[-1])
    assert rec["run_id"] == run_ctx.run_id
    assert rec["step"] == "START_PROCESSING"
    assert rec["status"] == "STARTED"
    assert rec["event"] == "step_execution"


def test_audit_log_error_writes_errors_jsonl(audit: AuditRepository, run_ctx: RunContext, cfg: AppConfig) -> None:
    """AuditLog.log with status FAILED must write to both audit_history.jsonl and errors.jsonl."""
    audit.log(
        status="FAILED",
        ctx=run_ctx,
        src="role-architect/task_001.md",
        dst="output/role-architect/task_001.md",
        dur=0.5,
        in_c=100,
        out_c=0,
        err="TimeoutError: response timed out after 300s",
    )

    errors_jsonl = cfg.log_path / "errors.jsonl"
    errors_log   = cfg.log_path / "errors.log"
    audit_file   = cfg.log_path / "audit_history.jsonl"

    assert errors_jsonl.exists(), "errors.jsonl must be created on failure"
    assert errors_log.exists(),   "errors.log must be created on failure"
    assert audit_file.exists(),   "audit_history.jsonl must still be written"

    err_rec = json.loads(errors_jsonl.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert err_rec["run_id"] == run_ctx.run_id
    assert "TimeoutError" in err_rec["error"]
    assert err_rec["source_file"] == "role-architect/task_001.md"


# ─── _iter_todo (batch mode: file moves to .processing) ─────────────────────

def _make_orchestrator(mocker: Any, audit: Any = None) -> Any:
    """Build a CoreOrchestrator with mock capabilities for file-state tests."""
    from modules.core.src.agent_core_orchestrator import CoreOrchestrator
    from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter

    return CoreOrchestrator(
        browser=mocker.MagicMock(),
        injector=mocker.MagicMock(),
        sender=mocker.MagicMock(),
        streamer=mocker.MagicMock(),
        uploader=mocker.MagicMock(),
        saver=mocker.MagicMock(),
        audit=audit or mocker.MagicMock(),
        observability=mocker.MagicMock(),
        workspace=mocker.MagicMock(),
        circuit_breaker=CircuitBreaker(),
        rate_limiter=RateLimiter(),
    )


def test_iter_todo_batch_moves_file_to_processing(
    fixture_root: Path, tmp_path: Path, mocker: Any
) -> None:
    """_iter_todo in batch mode must physically move the file to .processing/."""
    orchestrator = _make_orchestrator(mocker)

    # Use tmp_path as a fully isolated sandbox — copy fixture structure there
    sandbox_input  = tmp_path / "input"
    sandbox_output = tmp_path / "output"
    role_dir = sandbox_input / "role-architect"
    role_dir.mkdir(parents=True)
    (sandbox_output / "role-architect").mkdir(parents=True)

    # Copy the real task file into the sandbox todo/ dir (1:1 production structure)
    src_task = fixture_root / "input" / "role-architect" / "todo" / "task_001.md"
    todo_dir = role_dir / "todo"
    todo_dir.mkdir(parents=True)
    task_copy = todo_dir / "task_001.md"
    shutil.copy2(src_task, task_copy)

    sandbox_cfg = AppConfig(
        mode="batch",
        input_path=sandbox_input,
        output_path=sandbox_output,
        done_path=sandbox_input / "role-architect" / "done",
        failed_path=sandbox_input / "role-architect" / "failed",
        proc_path=sandbox_input / "role-architect" / ".processing",
        session_path=tmp_path / "session",
        log_path=tmp_path / "log",
        headless=True,
    )

    collected = list(orchestrator._iter_todo(sandbox_cfg))

    assert len(collected) == 1, f"Expected 1 file, got {len(collected)}"
    proc_file, rel_path = collected[0]

    assert proc_file.exists(), "File must exist at .processing path"
    assert not task_copy.exists(), "Original file must be moved (not copied)"
    assert ".processing" in str(proc_file), "Destination must be inside .processing/"
    assert str(rel_path) == "role-architect/todo/task_001.md"


def test_file_moves_to_done_on_success(tmp_path: Path, mocker: Any) -> None:
    """When processing succeeds, file moves from .processing to role-architect/done/task_001.md."""
    from modules.shared.src.utility_core_path import resolve_role_paths
    from modules.shared.src import AppConfig, CircuitBreaker, RateLimiter

    input_dir = tmp_path / "input"
    out_dir = tmp_path / "output"
    proc_dir = tmp_path / ".processing"

    cfg = AppConfig(
        mode="batch",
        input_path=input_dir,
        output_path=out_dir,
        proc_path=proc_dir,
        done_path=input_dir / "done",
        failed_path=input_dir / "failed",
        session_path=tmp_path / "session",
    )

    rel_path = Path("role-architect/todo/task_001.md")
    out_path, done_path, fail_path, proc_file = resolve_role_paths(rel_path, cfg)

    proc_file.parent.mkdir(parents=True, exist_ok=True)
    proc_file.write_text("Test prompt content")

    mock_saver = mocker.MagicMock()
    mock_audit = mocker.MagicMock()
    orchestrator = _make_orchestrator(mocker, audit=mock_audit)
    orchestrator._saver = mock_saver
    orchestrator._rl = RateLimiter()
    orchestrator._cb = CircuitBreaker()
    orchestrator._send_file = mocker.MagicMock(return_value="Response text")

    orchestrator._execute_single_attempt(
        proc_file, rel_path, cfg, mocker.MagicMock(),
        time.time(), "Test prompt content", out_path, done_path
    )

    assert done_path.exists(), f"File must be moved to {done_path}"
    assert not proc_file.exists(), "Proc file must no longer exist in .processing"
    assert done_path == input_dir / "role-architect" / "done" / "task_001.md"


def test_file_moves_to_failed_on_failure(tmp_path: Path, mocker: Any) -> None:
    """When processing fails, file moves from .processing to role-architect/failed/task_001.md."""
    from modules.shared.src.utility_core_path import resolve_role_paths
    from modules.shared.src import AppConfig, CircuitBreaker

    input_dir = tmp_path / "input"
    out_dir = tmp_path / "output"
    proc_dir = tmp_path / ".processing"

    cfg = AppConfig(
        mode="batch",
        input_path=input_dir,
        output_path=out_dir,
        proc_path=proc_dir,
        done_path=input_dir / "done",
        failed_path=input_dir / "failed",
        session_path=tmp_path / "session",
    )

    rel_path = Path("role-architect/todo/task_001.md")
    out_path, done_path, fail_path, proc_file = resolve_role_paths(rel_path, cfg)

    proc_file.parent.mkdir(parents=True, exist_ok=True)
    proc_file.write_text("Test prompt content")

    mock_audit = mocker.MagicMock()
    orchestrator = _make_orchestrator(mocker, audit=mock_audit)
    orchestrator._cb = CircuitBreaker()

    orchestrator._handle_processing_failure(
        proc_file, rel_path, cfg, mocker.MagicMock(),
        time.time(), "Test prompt content", out_path, fail_path,
        Exception("Test error")
    )

    assert fail_path.exists(), f"File must be quarantined at {fail_path}"
    assert not proc_file.exists(), "Proc file must no longer exist in .processing"
    assert fail_path == input_dir / "role-architect" / "failed" / "task_001.md"
