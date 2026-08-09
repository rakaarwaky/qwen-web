"""Pipeline fixture integration tests.

Every test calls a REAL production function from pipeline.py / config.py
directly against the tests/fixtures/ environment. No mocks, no invented logic.
The fixture environment is a 1:1 mirror of the production runtime structure.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

# These imports come from src/ via conftest.py sys.path injection
from pipeline import (
    AuditLog,
    _list_input_files,
    _write_output,
    load_role_prompt,
    resolve_role_paths,
)
from config import AppConfig, RunContext

ROLES = ["role-architect", "role-business-analyst", "role-tech-lead"]


# ─── _list_input_files ───────────────────────────────────────────────────────

def test_list_input_files_finds_tasks(cfg: AppConfig) -> None:
    """_list_input_files must find task_001.md in each role folder."""
    files = _list_input_files(cfg.input_path)
    rel_paths = [str(rel) for _, rel in files]

    for role in ROLES:
        expected = f"{role}/todo/task_001.md"
        assert any(expected in p for p in rel_paths), (
            f"Expected to find '{expected}' but got: {rel_paths}"
        )


def test_list_input_files_skips_prompt_md(cfg: AppConfig) -> None:
    """_list_input_files must skip PROMPT.md exactly as production does (line 227 pipeline.py)."""
    files = _list_input_files(cfg.input_path)
    rel_paths = [str(rel).upper() for _, rel in files]

    assert not any("PROMPT.MD" in p for p in rel_paths), (
        "PROMPT.md must be skipped by scanner — it is a role config, not a task"
    )


def test_list_input_files_skips_done_failed_processing(cfg: AppConfig, tmp_path: Path) -> None:
    """_list_input_files must skip done/, failed/, .processing/ subdirs."""
    # Place a file in each skip-dir to confirm it is ignored
    skip_dirs = ["done", "failed", ".processing"]
    created: list[Path] = []
    for d in skip_dirs:
        p = cfg.input_path / "role-architect" / d / "should_be_skipped.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("skip me", encoding="utf-8")
        created.append(p)

    try:
        files = _list_input_files(cfg.input_path)
        rel_paths = [str(rel) for _, rel in files]
        assert not any("should_be_skipped" in p for p in rel_paths), (
            f"Files in skip dirs must be excluded. Found: {rel_paths}"
        )
    finally:
        for p in created:
            p.unlink(missing_ok=True)


# ─── resolve_role_paths ──────────────────────────────────────────────────────

@pytest.mark.parametrize("role", ROLES)
def test_resolve_role_paths_structure(cfg: AppConfig, role: str) -> None:
    """resolve_role_paths must return paths rooted under the correct role folder.
    rel_path includes todo/ as production scanner returns it that way.
    resolve_role_paths strips todo/ internally (pipeline.py line 198-199).
    """
    rel_path = Path(role) / "todo" / "task_001.md"  # exactly what _iter_todo yields
    out_path, done_path, fail_path, proc_file = resolve_role_paths(rel_path, cfg)

    # output goes under cfg.output_path/<role>/
    assert str(out_path).startswith(str(cfg.output_path / role)), (
        f"out_path {out_path} must be under output/{role}/"
    )
    # done/failed/.processing stay inside input/<role>/
    assert role in str(done_path), f"done_path {done_path} must contain role folder"
    assert role in str(fail_path), f"fail_path {fail_path} must contain role folder"
    assert role in str(proc_file), f"proc_file {proc_file} must contain role folder"
    assert "done" in str(done_path)
    assert "failed" in str(fail_path)
    assert ".processing" in str(proc_file)


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

    _write_output(
        path=out_file,
        content=content,
        ctx=run_ctx,
        src="role-architect/task_001.md",
        dur=1.23,
        in_c=len("input"),
        out_c=len(content),
    )

    assert out_file.exists(), "Output file must be created by _write_output"
    text = out_file.read_text(encoding="utf-8")
    assert "METADATA TRACEABILITY" in text, "Header block must be present"
    assert run_ctx.run_id in text, "run_id must appear in traceability header"
    assert content in text, "Original content must follow the header"


# ─── AuditLog ────────────────────────────────────────────────────────────────

def test_audit_log_step_writes_valid_jsonl(audit: AuditLog, run_ctx: RunContext, cfg: AppConfig) -> None:
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


def test_audit_log_error_writes_errors_jsonl(audit: AuditLog, run_ctx: RunContext, cfg: AppConfig) -> None:
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

def test_iter_todo_batch_moves_file_to_processing(
    fixture_root: Path, tmp_path: Path
) -> None:
    """_iter_todo in batch mode must physically move the file to .processing/."""
    from pipeline import _iter_todo

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

    collected = list(_iter_todo(sandbox_cfg))

    assert len(collected) == 1, f"Expected 1 file, got {len(collected)}"
    proc_file, rel_path = collected[0]

    assert proc_file.exists(), "File must exist at .processing path"
    assert not task_copy.exists(), "Original file must be moved (not copied)"
    assert ".processing" in str(proc_file), "Destination must be inside .processing/"
    assert str(rel_path) == "role-architect/todo/task_001.md"
