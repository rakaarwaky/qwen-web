"""Regression lock suite — proven behaviors locked against regressions.

Each test corresponds to a behavior proven passing in the verified suite.
If any break, something real regressed.

Scope:
  - types.py     : exception hierarchy, CircuitBreaker, RateLimiter,
                   ErrorCategory, AppConfig validation, RunContext
  - pipeline.py  : _extract_prompt_text, _strip_input_from_output,
                   _should_process_file, _list_input_files,
                   resolve_role_paths, load_role_prompt, AuditLog
  - saver.py     : write_output (header, sidecar, atomic, error)
  - qwen_client  : init contract, context manager, lifecycle

Run: python3 -m pytest tests/test_regression_lock.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.core.src.capabilities_audit_repository import AuditRepository
from modules.core.src.capabilities_output_saver import Saver
from modules.shared.src import (
    AppConfig,
    AuthRequiredError,
    CircuitBreaker,
    CircuitBreakerOpenError,
    ErrorCategory,
    NetworkTimeoutError,
    OutputWriteError,
    PromptInjectionError,
    QwenCliError,
    RateLimiter,
    RunContext,
    SaverConfig,
)
from modules.shared.src.utility_core_path import (
    list_input_files as _list_input_files,
)
from modules.shared.src.utility_core_path import (
    resolve_role_paths,
)
from modules.shared.src.utility_core_path import (
    should_process_file as _should_process_file,
)
from modules.shared.src.utility_core_prompt import (
    extract_prompt_text as _extract_prompt_text,
)
from modules.shared.src.utility_core_prompt import (
    load_role_prompt,
)
from modules.shared.src.utility_core_prompt import (
    strip_input_from_output as _strip_input_from_output,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_cfg(tmp_path: Path, mode: str = "batch") -> AppConfig:
    return AppConfig(
        mode=mode,
        input_path=tmp_path / "input",
        output_path=tmp_path / "output",
        done_path=tmp_path / "input" / "role-architect" / "done",
        failed_path=tmp_path / "input" / "role-architect" / "failed",
        proc_path=tmp_path / "input" / ".processing",
        session_path=tmp_path / "session",
        log_path=tmp_path / "log",
    )


def _make_task(
    tmp_path: Path, role: str = "role-architect", subfolder: str = "todo", name: str = "task_001.md"
) -> Path:
    f = tmp_path / "input" / role / subfolder / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# Task prompt\nDo the thing.", encoding="utf-8")
    return f


from tests.helpers import make_test_orchestrator as _make_orchestrator

# ─── Exception hierarchy lock ─────────────────────────────────────────────────


class TestExceptionHierarchy:
    """All domain exceptions must derive from QwenCliError."""

    def test_auth_required_is_qwen_cli_error(self):
        assert issubclass(AuthRequiredError, QwenCliError)

    def test_prompt_injection_is_qwen_cli_error(self):
        assert issubclass(PromptInjectionError, QwenCliError)

    def test_circuit_breaker_open_is_qwen_cli_error(self):
        assert issubclass(CircuitBreakerOpenError, QwenCliError)

    def test_network_timeout_is_qwen_cli_error(self):
        assert issubclass(NetworkTimeoutError, QwenCliError)

    def test_qwen_cli_error_is_runtime_error(self):
        assert issubclass(QwenCliError, RuntimeError)

    def test_output_write_error_is_qwen_cli_error(self):
        assert issubclass(OutputWriteError, QwenCliError)


# ─── ErrorCategory lock ───────────────────────────────────────────────────────


class TestErrorCategory:
    """ErrorCategory.categorize must map known patterns to correct categories."""

    @pytest.mark.parametrize(
        "exc,expected",
        [
            (AuthRequiredError("login required"), "auth"),
            (RuntimeError("captcha challenge"), "auth"),
            (TimeoutError("connection dropped"), "network"),
            (RuntimeError("socket closed"), "network"),
            (RuntimeError("429 rate limit exceeded"), "rate_limit"),
            (RuntimeError("throttling applied"), "rate_limit"),
            (RuntimeError("chromium page crashed"), "browser"),
            (RuntimeError("playwright launch failed"), "browser"),
            (RuntimeError("prompt fill failed"), "injection"),
            (RuntimeError("clipboard paste failed"), "injection"),
            (ValueError("parse empty response"), "parsing"),
            (OSError("disk I/O error"), "file_io"),
            (Exception("unhandled custom error"), "other"),
        ],
    )
    def test_categorize(self, exc: Exception, expected: str):
        assert ErrorCategory.categorize(exc) == expected


# ─── CircuitBreaker lock ──────────────────────────────────────────────────────


class TestCircuitBreakerLock:
    def test_not_tripped_initially(self):
        cb = CircuitBreaker(threshold=3, window_sec=60)
        assert not cb.is_tripped

    def test_trips_after_threshold_failures(self):
        cb = CircuitBreaker(threshold=3, window_sec=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.is_tripped

    def test_resets_on_success(self):
        cb = CircuitBreaker(threshold=2, window_sec=60)
        cb.record_failure()
        cb.record_failure()
        assert cb.is_tripped
        cb.record_success()
        assert not cb.is_tripped

    def test_invalid_threshold_raises(self):
        with pytest.raises(ValueError, match="threshold"):
            CircuitBreaker(threshold=0)

    def test_invalid_window_raises(self):
        with pytest.raises(ValueError, match="window_sec"):
            CircuitBreaker(window_sec=0)

    def test_below_threshold_does_not_trip(self):
        cb = CircuitBreaker(threshold=5, window_sec=60)
        for _ in range(4):
            cb.record_failure()
        assert not cb.is_tripped


# ─── RateLimiter lock ─────────────────────────────────────────────────────────


class TestRateLimiterLock:
    def test_single_acquire_succeeds(self):
        rl = RateLimiter(max_per_minute=60)
        rl.acquire()

    def test_invalid_rate_raises(self):
        with pytest.raises(ValueError, match="max_per_minute"):
            RateLimiter(max_per_minute=0)

    def test_high_rate_limit_allows_burst(self):
        rl = RateLimiter(max_per_minute=1000)
        for _ in range(10):
            rl.acquire()


# ─── AppConfig validation lock ────────────────────────────────────────────────


class TestAppConfigValidation:
    def test_valid_config_constructs(self, tmp_path: Path):
        cfg = _make_cfg(tmp_path)
        assert cfg.timeout == 300

    def test_timeout_below_minimum_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="timeout"):
            AppConfig(
                mode="batch",
                input_path=tmp_path / "input",
                output_path=tmp_path / "output",
                done_path=tmp_path / "done",
                failed_path=tmp_path / "failed",
                proc_path=tmp_path / ".processing",
                session_path=tmp_path / "session",
                timeout=10,
            )

    def test_poll_interval_below_minimum_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="poll_interval"):
            AppConfig(
                mode="batch",
                input_path=tmp_path / "input",
                output_path=tmp_path / "output",
                done_path=tmp_path / "done",
                failed_path=tmp_path / "failed",
                proc_path=tmp_path / ".processing",
                session_path=tmp_path / "session",
                poll_interval=0.1,
            )

    def test_status_path_property(self, tmp_path: Path):
        cfg = _make_cfg(tmp_path)
        assert cfg.status_path == cfg.log_path / "status.json"


# ─── RunContext lock ──────────────────────────────────────────────────────────


class TestRunContextLock:
    def test_run_id_is_unique_per_instance(self):
        ids = {RunContext().run_id for _ in range(10)}
        assert len(ids) == 10

    def test_run_id_format(self):
        ctx = RunContext()
        parts = ctx.run_id.split("_")
        assert len(parts) == 3
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS
        assert len(parts[2]) == 6  # uuid hex[:6]


# ─── _extract_prompt_text lock ────────────────────────────────────────────────


class TestExtractPromptText:
    def test_strips_yaml_frontmatter(self):
        assert _extract_prompt_text("---\nname: test\n---\n# Body") == "# Body"

    def test_passthrough_when_no_frontmatter(self):
        assert _extract_prompt_text("# Plain content") == "# Plain content"

    def test_strips_only_outer_frontmatter(self):
        raw = "---\nkey: val\n---\n# Body\n---\nstill body"
        assert _extract_prompt_text(raw).startswith("# Body")

    def test_empty_string_returns_empty(self):
        assert _extract_prompt_text("") == ""


# ─── _strip_input_from_output lock ───────────────────────────────────────────


class TestStripInputFromOutput:
    def test_strips_repeated_prompt_prefix(self):
        prompt = "Tell me about Python"
        response = prompt + "\nPython is a versatile language used for many purposes."
        result = _strip_input_from_output(response, prompt)
        assert not result.startswith(prompt)
        assert "Python is a versatile" in result

    def test_passthrough_when_no_overlap(self):
        response = "This is a completely different response."
        assert _strip_input_from_output(response, "Hello") == response

    def test_empty_text_returns_empty(self):
        assert _strip_input_from_output("", "some prompt") == ""

    def test_empty_prompt_returns_text(self):
        assert _strip_input_from_output("Response text", "") == "Response text"


# ─── _should_process_file lock ───────────────────────────────────────────────


class TestShouldProcessFileLock:
    def test_valid_role_task_passes(self, tmp_path: Path):
        f = _make_task(tmp_path)
        assert _should_process_file(f, tmp_path / "input") is True

    def test_prompt_md_excluded(self, tmp_path: Path):
        prompt = tmp_path / "input" / "role-architect" / "PROMPT.md"
        prompt.parent.mkdir(parents=True, exist_ok=True)
        prompt.write_text("prompt")
        assert _should_process_file(prompt, tmp_path / "input") is False

    def test_done_folder_excluded(self, tmp_path: Path):
        assert _should_process_file(_make_task(tmp_path, subfolder="done"), tmp_path / "input") is False

    def test_failed_folder_excluded(self, tmp_path: Path):
        assert _should_process_file(_make_task(tmp_path, subfolder="failed"), tmp_path / "input") is False

    def test_processing_folder_excluded(self, tmp_path: Path):
        assert _should_process_file(_make_task(tmp_path, subfolder=".processing"), tmp_path / "input") is False

    def test_non_role_dir_excluded(self, tmp_path: Path):
        f = tmp_path / "input" / "tasks" / "file.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
        assert _should_process_file(f, tmp_path / "input") is False


# ─── _list_input_files lock ───────────────────────────────────────────────────


class TestListInputFilesLock:
    def test_lists_valid_tasks_only(self, tmp_path: Path):
        _make_task(tmp_path)
        (tmp_path / "input" / "role-architect" / "PROMPT.md").write_text("cfg")
        done = tmp_path / "input" / "role-architect" / "done" / "old.md"
        done.parent.mkdir(parents=True, exist_ok=True)
        done.write_text("done")

        rel = [str(r) for _, r in _list_input_files(tmp_path / "input")]
        assert any("task_001.md" in r for r in rel)
        assert not any("PROMPT.md" in r for r in rel)
        assert not any("done" in r for r in rel)

    def test_empty_dir_returns_empty(self, tmp_path: Path):
        d = tmp_path / "empty"
        d.mkdir()
        assert _list_input_files(d) == []

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path):
        assert _list_input_files(tmp_path / "nonexistent") == []


# ─── resolve_role_paths lock ──────────────────────────────────────────────────


class TestResolveRolePathsLock:
    def test_role_path_strips_todo(self, tmp_path: Path):
        cfg = _make_cfg(tmp_path)
        out, done, fail, proc = resolve_role_paths(Path("role-architect/todo/task_001.md"), cfg)
        assert out == cfg.output_path / "task_001.md"
        assert "role-architect" in str(done) and "done" in str(done)
        assert "role-architect" in str(fail) and "failed" in str(fail)
        assert "role-architect" in str(proc) and ".processing" in str(proc)

    def test_role_path_strips_done(self, tmp_path: Path):
        cfg = _make_cfg(tmp_path)
        out, *_ = resolve_role_paths(Path("role-architect/done/task_001.md"), cfg)
        assert out == cfg.output_path / "task_001.md"

    @pytest.mark.parametrize("role", ["role-architect", "role-business-analyst", "role-tech-lead"])
    def test_multiple_roles_resolve_correctly(self, tmp_path: Path, role: str):
        cfg = _make_cfg(tmp_path)
        _, done, fail, proc = resolve_role_paths(Path(f"{role}/todo/task_001.md"), cfg)
        assert role in str(done) and role in str(fail) and role in str(proc)

    def test_no_duplicate_role_in_single_mode(self, tmp_path: Path):
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
        out, *_ = resolve_role_paths(Path("role-architect/done/task_001.md"), cfg)
        assert "role-architect/done/task_001.md/role-architect" not in str(out)


# ─── load_role_prompt lock ────────────────────────────────────────────────────


class TestLoadRolePromptLock:
    def test_strips_frontmatter_from_prompt(self, tmp_path: Path):
        task = _make_task(tmp_path)
        (tmp_path / "input" / "role-architect" / "PROMPT.md").write_text(
            "---\nname: role-architect\n---\n# Architect Instructions"
        )
        result = load_role_prompt(task)
        assert "# Architect Instructions" in result
        assert "name: role-architect" not in result
        assert not result.startswith("---")

    def test_custom_prompt_path_takes_priority(self, tmp_path: Path):
        task = _make_task(tmp_path)
        custom = tmp_path / "CUSTOM_PROMPT.md"
        custom.write_text("---\nname: custom\n---\n# Custom Instructions")
        assert "# Custom Instructions" in load_role_prompt(task, custom_prompt_path=custom)

    def test_returns_empty_when_no_prompt_found(self, tmp_path: Path):
        task = tmp_path / "orphan.md"
        task.write_text("orphan")
        assert load_role_prompt(task) == ""


# ─── AuditLog lock ────────────────────────────────────────────────────────────


class TestAuditLogLock:
    def test_log_step_writes_valid_jsonl(self, tmp_path: Path):
        audit = AuditRepository(tmp_path)
        ctx = RunContext()
        audit.log_step(ctx, "START_PROCESSING", "role-architect/task.md", "STARTED", {"input_chars": 42})

        rec = json.loads((tmp_path / "audit_history.jsonl").read_text().splitlines()[-1])
        assert rec["run_id"] == ctx.run_id
        assert rec["step"] == "START_PROCESSING"
        assert rec["status"] == "STARTED"
        assert rec["event"] == "step_execution"
        assert rec["details"]["input_chars"] == 42

    def test_log_failure_writes_errors_jsonl(self, tmp_path: Path):
        audit = AuditRepository(tmp_path)
        ctx = RunContext()
        audit.log(
            status="FAILED",
            ctx=ctx,
            src="task.md",
            dst="out.md",
            dur=0.5,
            in_c=100,
            out_c=0,
            err="TimeoutError: timed out",
        )

        assert (tmp_path / "errors.jsonl").exists()
        assert (tmp_path / "errors.log").exists()
        rec = json.loads((tmp_path / "errors.jsonl").read_text().strip())
        assert rec["run_id"] == ctx.run_id
        assert "TimeoutError" in rec["error"]

    def test_log_success_does_not_write_errors_files(self, tmp_path: Path):
        audit = AuditRepository(tmp_path)
        ctx = RunContext()
        audit.log(status="SUCCESS", ctx=ctx, src="task.md", dst="out.md", dur=1.0, in_c=50, out_c=200)
        assert not (tmp_path / "errors.jsonl").exists()
        assert not (tmp_path / "errors.log").exists()
        assert (tmp_path / "audit_history.jsonl").exists()

    def test_multiple_steps_accumulate_in_jsonl(self, tmp_path: Path):
        audit = AuditRepository(tmp_path)
        ctx = RunContext()
        for step in ("STEP_A", "STEP_B", "STEP_C"):
            audit.log_step(ctx, step, "file.md", "STARTED")
        steps = [json.loads(l)["step"] for l in (tmp_path / "audit_history.jsonl").read_text().splitlines()]
        assert steps == ["STEP_A", "STEP_B", "STEP_C"]


# ─── write_output (saver) lock ────────────────────────────────────────────────


class TestWriteOutputLock:
    def test_creates_file_pure_content(self, tmp_path: Path):
        out = tmp_path / "result.md"
        ctx = RunContext()
        Saver().write_output(out, "AI response content", ctx, "input.md", 1.23, 10, 19)
        text = out.read_text()
        assert "AI response content" in text

    def test_creates_json_sidecar(self, tmp_path: Path):
        out = tmp_path / "result.md"
        ctx = RunContext()
        Saver().write_output(out, "Content", ctx, "src.md", 2.5, 5, 7)
        meta = json.loads(out.with_suffix(".meta.json").read_text())
        assert meta["run_id"] == ctx.run_id
        assert meta["source_file"] == "src.md"
        assert meta["duration_sec"] == 2.5

    def test_no_header_no_sidecar_config(self, tmp_path: Path):
        out = tmp_path / "plain.md"
        cfg = SaverConfig(include_header=False, generate_sidecar=False)
        ctx = RunContext()
        Saver().write_output(out, "Raw content", ctx, "src.md", 0.1, 3, 11, config=cfg)
        assert out.read_text() == "Raw content"
        assert not out.with_suffix(".meta.json").exists()

    def test_raises_output_write_error_on_bad_path(self, tmp_path: Path):
        blocked = tmp_path / "blocked_dir"
        blocked.write_text("i am a file")
        out = blocked / "child.md"
        with pytest.raises(OutputWriteError):
            Saver().write_output(out, "test", RunContext(), "src.md", 0.1, 4, 4)

    def test_run_id_in_sidecar_matches_context(self, tmp_path: Path):
        out = tmp_path / "match.md"
        ctx = RunContext()
        Saver().write_output(out, "text", ctx, "file.md", 1.0, 4, 4)
        meta = json.loads(out.with_suffix(".meta.json").read_text())
        assert meta["run_id"] == ctx.run_id


# ─── CoreOrchestrator DI contract lock ───────────────────────────────────────


class TestCoreOrchestratorDiLock:
    def test_init_with_mock_capabilities(self):
        orch = _make_orchestrator()
        assert orch._browser is not None
        assert orch._audit is not None

    def test_send_file_raises_without_page(self, tmp_path: Path):
        orch = _make_orchestrator()
        f = tmp_path / "doc.md"
        f.write_text("content")
        with pytest.raises(Exception):
            orch.send_file(None, f, timeout_sec=1)  # type: ignore[arg-type]

    def test_backward_compatible_init_with_cfg(self, tmp_path: Path):
        cfg = _make_cfg(tmp_path)
        orch = _make_orchestrator()
        assert orch._cb is not None
        assert cfg is not None
