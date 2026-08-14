"""Capabilities: audit log repository (AES403).

Implements IAuditProtocol — structured JSONL audit history, error traces,
step-level context, and audit-log reads. Workspace provisioning delegates to
IWorkspaceProtocol via DI. All file system I/O for the domain lives here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.core.src.utility_core_io_writer import append_jsonl, ensure_dir
from modules.shared.src import (
    DEFAULT_LOG,
    FilePath,
    IAuditProtocol,
    IWorkspaceProtocol,
    ResponseText,
    RunContext,
    utc_now_iso,
)

# Block 1: Class Definition & Constructor


class AuditRepository(IAuditProtocol):
    """Structured JSONL audit log with error traces and step-level context."""

    def __init__(self, log_dir: Path | None = None, workspace: IWorkspaceProtocol | None = None) -> None:
        """Initialize audit log files in the target directory."""
        target_dir = log_dir or DEFAULT_LOG
        ensure_dir(target_dir)
        self._audit = target_dir / "audit_history.jsonl"
        self._errors = target_dir / "errors.log"
        self._errors_jsonl = target_dir / "errors.jsonl"
        self._workspace = workspace

    # ─── Block 2: Public Contract (IAuditProtocol ONLY) ──

    def log_step(
        self,
        ctx: RunContext,
        step: str,
        src: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log granular step-by-step event execution for end-to-end traceability."""
        rec: dict[str, Any] = {
            "run_id": ctx.run_id,
            "timestamp": utc_now_iso(),
            "event": "step_execution",
            "step": step,
            "source_file": src,
            "status": status,
        }
        if details is not None:
            rec["details"] = details
        append_jsonl(self._audit, rec)

    def log(
        self,
        status: str,
        ctx: RunContext,
        src: str,
        dst: str,
        dur: float,
        in_c: int,
        out_c: int,
        err: str = "",
    ) -> None:
        """Log a completed file processing result with duration and character counts."""
        rec = {
            "run_id": ctx.run_id,
            "timestamp": utc_now_iso(),
            "source_file": src,
            "output_file": dst,
            "status": status,
            "duration_sec": dur,
            "input_chars": in_c,
            "output_chars": out_c,
        }
        if err:
            rec["error"] = err
        append_jsonl(self._audit, rec)
        if err:
            err_entry = f"[{utc_now_iso()}] [run_id={ctx.run_id}] {src}: {err}\n\n"
            with self._errors.open("a", encoding="utf-8") as f:
                f.write(err_entry)

            err_json_rec = {
                "run_id": ctx.run_id,
                "timestamp": utc_now_iso(),
                "source_file": src,
                "output_file": dst,
                "error": err,
                "duration_sec": dur,
                "input_chars": in_c,
            }
            append_jsonl(self._errors_jsonl, err_json_rec)

    def init_workspace(self, target_dir: FilePath) -> None:
        """Delegate to workspace provisioner (separate concern via DI)."""
        if self._workspace is not None:
            self._workspace.init_workspace(FilePath(str(target_dir)))

    def get_audit_log(self, limit: int = 20) -> ResponseText:
        """Fetch recent entries without loading the complete JSONL file."""
        audit_file = self._audit
        if not audit_file.exists():
            return ResponseText("Audit log file does not exist yet.")
        if limit <= 0:
            return ResponseText("[]")

        records = _read_recent_jsonl_records(audit_file, limit)
        records.reverse()
        return ResponseText(json.dumps(records, indent=2))

    # Block 3: Dunder Methods, Factories & Helpers

    def __repr__(self) -> str:
        """Return string representation of AuditRepository."""
        return f"AuditRepository(log_dir={self._audit.parent!r})"


_AUDIT_READ_BLOCK_SIZE = 64 * 1024


def _read_recent_jsonl_records(audit_file: Path, limit: int) -> list[Any]:
    """Read at most ``limit`` valid JSONL records from the end of a file.

    Reading backwards in fixed-size blocks keeps memory bounded by the block
    size plus the requested result count. Blank, malformed, and undecodable
    lines are ignored so a partially written final record cannot hide older
    valid audit entries.
    """
    records: list[Any] = []
    pending = b""
    with audit_file.open("rb") as stream:
        position = stream.seek(0, 2)
        while position > 0 and len(records) < limit:
            block_size = min(_AUDIT_READ_BLOCK_SIZE, position)
            position -= block_size
            stream.seek(position)
            pending = stream.read(block_size) + pending
            lines = pending.split(b"\n")
            pending = lines[0]
            for raw_line in reversed(lines[1:]):
                record = _decode_jsonl_record(raw_line)
                if record is not None:
                    records.append(record)
                    if len(records) >= limit:
                        break

        if pending and len(records) < limit:
            record = _decode_jsonl_record(pending)
            if record is not None:
                records.append(record)

    return records


def _decode_jsonl_record(raw_line: bytes) -> Any | None:
    """Decode one JSONL line, returning ``None`` for blank or partial data."""
    try:
        line = raw_line.strip().decode("utf-8")
        if not line:
            return None
        return json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
