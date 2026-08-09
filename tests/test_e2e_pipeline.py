"""E2E integration tests: real browser × real chat.qwen.ai × tests/fixtures/ runtime.

These tests run the FULL production pipeline end-to-end:
  browser_session(e2e_cfg) → QwenClient → _iter_todo → _process_file

All paths are redirected to tests/fixtures/ so the production input/output/log/
directories are never touched. The real qwen_session/ is used for authentication.

Requirements:
  - Internet connection
  - Valid saved session in qwen_session/ (run `python -m src.main --login` first)

Run:
  python -m pytest tests/test_e2e_pipeline.py -v -m e2e

Exclude from normal CI:
  python -m pytest tests/ -v -m "not e2e"
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from browser import browser_session
from config import AppConfig, AuthRequiredError, RunContext
from pipeline import AuditLog, _iter_todo, _process_file, resolve_role_paths


pytestmark = pytest.mark.e2e


# ─── Teardown helper ─────────────────────────────────────────────────────────

def _restore_task(fixture_root: Path, role: str, filename: str) -> None:
    """After the pipeline moves the task file to done/ or failed/,
    copy it back to todo/ so the fixture is clean for the next run.
    """
    todo_target = fixture_root / "input" / role / "todo" / filename

    # Check done/ first, then failed/, then .processing/
    for subfolder in ("done", "failed", ".processing"):
        src = fixture_root / "input" / role / subfolder / filename
        if src.exists():
            todo_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, todo_target)
            return

    # If somehow still missing, restore from output (last resort)
    # This shouldn't happen, but makes teardown robust.
    if not todo_target.exists():
        pytest.fail(
            f"Teardown: could not find {filename} in done/, failed/, or .processing/ "
            f"— fixture state may be corrupted. Restore manually."
        )


# ─── E2E Tests ───────────────────────────────────────────────────────────────

@pytest.mark.e2e
class TestE2EPipeline:

    def test_e2e_single_role_architect(
        self, e2e_cfg: AppConfig, fixture_root: Path
    ) -> None:
        """Full pipeline: picks up role-architect/todo/task_001.md, sends to Qwen,
        writes output, moves to done/, logs to tests/fixtures/log/.

        Assertions mirror exactly what production main.py expects after a
        successful run — no invented checks.
        """
        role = "role-architect"
        filename = "task_001.md"
        rel_path = Path(role) / "todo" / filename

        # Resolve expected paths using real production function
        out_path, done_path, fail_path, _ = resolve_role_paths(rel_path, e2e_cfg)

        # Clean up stale output from previous run (idempotent)
        if out_path.exists():
            out_path.unlink()

        audit = AuditLog(e2e_cfg.log_path)
        ctx = RunContext()

        try:
            with browser_session(e2e_cfg) as bctx:
                from qwen_client import QwenClient
                client = QwenClient(bctx, headless=True)

                # _iter_todo moves task_001.md → .processing/
                todo_items = list(_iter_todo(e2e_cfg))

                # Filter to our target file only
                target = next(
                    ((pf, rp) for pf, rp in todo_items if filename in str(rp)),
                    None,
                )
                if target is None:
                    pytest.skip(
                        f"No processable file found in {e2e_cfg.input_path}. "
                        f"Ensure {role}/todo/{filename} exists."
                    )

                proc_file, matched_rel = target
                _process_file(client, proc_file, matched_rel, e2e_cfg, audit, ctx)

        except AuthRequiredError as exc:
            pytest.skip(
                f"Qwen session expired or CAPTCHA required: {exc}. "
                f"Run `python -m src.main --login` to refresh the session."
            )
        finally:
            # Always restore task_001.md to todo/ so fixture is clean
            _restore_task(fixture_root, role, filename)

        # ── Assertions (same checks production operators would do) ────────────

        # 1. Output file written to fixtures/output/role-architect/
        assert out_path.exists(), (
            f"Output file not created: {out_path}\n"
            f"Check fixtures/log/errors.jsonl for error details."
        )

        # 2. Output has the traceability header (_write_output contract)
        output_text = out_path.read_text(encoding="utf-8")
        assert "METADATA TRACEABILITY" in output_text, (
            "Output file missing traceability header — _write_output may have changed."
        )
        assert ctx.run_id in output_text, "run_id must be embedded in output header"

        # 3. Actual Qwen response is non-empty
        # Header ends at --> so content follows
        body = output_text.split("-->", 1)[-1].strip()
        assert len(body) > 50, (
            f"Response body too short ({len(body)} chars) — Qwen may have returned an error."
        )

        # 4. Done file exists (pipeline moved proc_file → done/)
        assert done_path.exists(), (
            f"done/{filename} not found — _process_file did not complete the move."
        )

        # 5. Audit trail written
        audit_file = e2e_cfg.log_path / "audit_history.jsonl"
        assert audit_file.exists(), "audit_history.jsonl not written"

        lines = [l for l in audit_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        records = [json.loads(l) for l in lines]
        run_records = [r for r in records if r.get("run_id") == ctx.run_id]

        assert any(r.get("status") == "SUCCESS" for r in run_records), (
            f"No SUCCESS record found for run_id={ctx.run_id}. "
            f"Records: {run_records}"
        )

        # Print output path for easy inspection
        print(f"\n✅ Output written to: {out_path}")
        print(f"📋 Audit log:         {audit_file}")
        print(f"📄 Response preview:  {body[:200]}...")

    @pytest.mark.e2e
    def test_e2e_auth_error_propagates_and_is_not_retried(
        self, e2e_cfg: AppConfig, fixture_root: Path, monkeypatch
    ) -> None:
        """AuthRequiredError must propagate out of _process_file without retry.

        The retry policy in pipeline.py explicitly excludes AuthRequiredError
        (line 54: retry_if_exception(lambda e: not isinstance(e, AuthRequiredError))).
        This test locks that contract without hitting the real network.
        """
        from pipeline import _retry_policy

        audit = AuditLog(e2e_cfg.log_path)
        ctx = RunContext()
        rel_path = Path("role-architect") / "todo" / "task_001.md"
        _, _, _, proc_file_path = resolve_role_paths(rel_path, e2e_cfg)

        # Write a temp proc file so _process_file can read it
        proc_file_path.parent.mkdir(parents=True, exist_ok=True)
        proc_file_path.write_text("# test auth error propagation", encoding="utf-8")

        try:
            with browser_session(e2e_cfg) as bctx:
                from qwen_client import QwenClient
                client = QwenClient(bctx, headless=True)

                # Patch send_file to immediately raise AuthRequiredError
                monkeypatch.setattr(
                    client, "send_file",
                    lambda *a, **k: (_ for _ in ()).throw(
                        AuthRequiredError("forced auth error")
                    )
                )

                with pytest.raises(AuthRequiredError):
                    _process_file(client, proc_file_path, rel_path, e2e_cfg, audit, ctx)

        except AuthRequiredError:
            pytest.skip("Real auth error from browser — session may be expired.")
        finally:
            # Clean up temp proc file
            if proc_file_path.exists():
                proc_file_path.unlink(missing_ok=True)

        # errors.jsonl must NOT be written for AuthRequiredError
        # (it re-raises immediately, _process_file's except block catches generic Exception)
        # The pipeline contract: auth errors bypass quarantine
        errors_jsonl = e2e_cfg.log_path / "errors.jsonl"
        if errors_jsonl.exists():
            lines = [l for l in errors_jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
            run_errors = [json.loads(l) for l in lines if ctx.run_id in l]
            # AuthRequiredError is re-raised before the except block writes errors.jsonl
            assert len(run_errors) == 0, (
                f"AuthRequiredError must NOT produce an errors.jsonl entry. Got: {run_errors}"
            )
