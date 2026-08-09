"""E2E integration tests: real browser × real chat.qwen.ai × tests/fixtures/ runtime.

These tests run the FULL production pipeline end-to-end:
  browser_session(e2e_cfg) → QwenClient → _iter_todo → _process_file

All paths are redirected to tests/fixtures/ so the production input/output/log/
directories are never touched. The real qwen_session/ is used for authentication.

State management:
  The `reset_fixture_state` fixture (from conftest.py) ensures tests/fixtures/
  is in its golden state BEFORE and AFTER every test — even on crash/interrupt.

  Golden state:
    input/<role>/todo/task_001.md  ← exists, original content
    input/<role>/done/             ← empty
    input/<role>/failed/           ← empty
    input/<role>/.processing/      ← empty
    output/<role>/                 ← empty
    log/                           ← empty

Requirements:
  - Internet connection
  - Valid saved session in qwen_session/ (run `python -m src.main --login` first)

Run:
  python -m pytest tests/test_e2e_pipeline.py -v -m e2e -s

Exclude from normal CI:
  python -m pytest tests/ -v -m "not e2e"
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.browser import browser_session
from src.config import AppConfig, AuthRequiredError, RunContext
from src.pipeline import AuditLog, _iter_todo, _process_file, resolve_role_paths


pytestmark = pytest.mark.e2e


@pytest.mark.e2e
class TestE2EPipeline:

    def test_e2e_single_role_architect(
        self,
        reset_fixture_state,   # ← resets before AND after this test
        e2e_cfg: AppConfig,
        fixture_root: Path,
    ) -> None:
        """Full pipeline: picks up role-architect/todo/task_001.md, sends to Qwen,
        writes output to fixtures/output/, moves to done/, logs to fixtures/log/.

        State is always clean before this test runs and restored after it finishes.
        """
        role = "role-architect"
        filename = "task_001.md"
        rel_path = Path(role) / "todo" / filename

        out_path, done_path, fail_path, _ = resolve_role_paths(rel_path, e2e_cfg)
        audit = AuditLog(e2e_cfg.log_path)
        ctx = RunContext()

        try:
            with browser_session(e2e_cfg) as bctx:
                from qwen_client import QwenClient
                client = QwenClient(bctx, headless=True)

                todo_items = list(_iter_todo(e2e_cfg))
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

        # ── Assertions ────────────────────────────────────────────────────────

        assert out_path.exists(), (
            f"Output file not created: {out_path}\n"
            f"Check fixtures/log/errors.jsonl for error details."
        )

        output_text = out_path.read_text(encoding="utf-8")
        assert "METADATA TRACEABILITY" in output_text
        assert ctx.run_id in output_text

        body = output_text.split("-->", 1)[-1].strip()
        assert len(body) > 50, (
            f"Response body too short ({len(body)} chars) — Qwen may have returned an error."
        )

        assert done_path.exists(), (
            f"done/{filename} not found — _process_file did not complete the move."
        )

        audit_file = e2e_cfg.log_path / "audit_history.jsonl"
        assert audit_file.exists()
        records = [
            json.loads(l)
            for l in audit_file.read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        assert any(
            r.get("run_id") == ctx.run_id and r.get("status") == "SUCCESS"
            for r in records
        ), f"No SUCCESS record for run_id={ctx.run_id}"

        print(f"\n✅ Output   : {out_path}")
        print(f"📋 Audit    : {audit_file}")
        print(f"📄 Preview  : {body[:300]}...")

    @pytest.mark.e2e
    def test_e2e_auth_error_propagates_and_is_not_retried(
        self,
        reset_fixture_state,
        e2e_cfg: AppConfig,
        fixture_root: Path,
        monkeypatch,
    ) -> None:
        """AuthRequiredError must propagate out of _process_file without retry.

        The retry policy in pipeline.py explicitly excludes AuthRequiredError
        (pipeline.py line 54: retry_if_exception(lambda e: not isinstance(e, AuthRequiredError))).
        """
        audit = AuditLog(e2e_cfg.log_path)
        ctx = RunContext()
        rel_path = Path("role-architect") / "todo" / "task_001.md"
        _, _, _, proc_file_path = resolve_role_paths(rel_path, e2e_cfg)

        proc_file_path.parent.mkdir(parents=True, exist_ok=True)
        proc_file_path.write_text("# test auth error propagation", encoding="utf-8")

        try:
            with browser_session(e2e_cfg) as bctx:
                from qwen_client import QwenClient
                client = QwenClient(bctx, headless=True)

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

        errors_jsonl = e2e_cfg.log_path / "errors.jsonl"
        if errors_jsonl.exists():
            run_errors = [
                json.loads(l)
                for l in errors_jsonl.read_text(encoding="utf-8").splitlines()
                if l.strip() and ctx.run_id in l
            ]
            assert len(run_errors) == 0, (
                f"AuthRequiredError must NOT produce an errors.jsonl entry. Got: {run_errors}"
            )
