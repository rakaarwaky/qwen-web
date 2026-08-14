from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from modules.core.src import capabilities_audit_repository as audit_module
from modules.core.src.capabilities_audit_repository import AuditRepository


def _records(response: str) -> list[dict[str, int]]:
    return json.loads(response)


def test_get_audit_log_missing_file_returns_contract_message(tmp_path: Path) -> None:
    result = AuditRepository(tmp_path).get_audit_log()

    assert result == "Audit log file does not exist yet."


def test_get_audit_log_empty_file_returns_empty_json_array(tmp_path: Path) -> None:
    (tmp_path / "audit_history.jsonl").write_text("", encoding="utf-8")

    assert AuditRepository(tmp_path).get_audit_log() == "[]"


def test_get_audit_log_reads_last_non_empty_valid_records(tmp_path: Path) -> None:
    audit_file = tmp_path / "audit_history.jsonl"
    audit_file.write_text(
        "\n".join(
            [
                json.dumps({"id": 1}),
                "",
                "not-json",
                json.dumps({"id": 2}),
                json.dumps({"id": 3}),
                '{"id": 4',
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert _records(AuditRepository(tmp_path).get_audit_log(limit=2)) == [{"id": 2}, {"id": 3}]


def test_get_audit_log_zero_or_negative_limit_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "audit_history.jsonl").write_text(json.dumps({"id": 1}) + "\n", encoding="utf-8")

    assert AuditRepository(tmp_path).get_audit_log(limit=0) == "[]"
    assert AuditRepository(tmp_path).get_audit_log(limit=-1) == "[]"


def test_get_audit_log_does_not_use_full_file_read_and_handles_large_tail(tmp_path: Path) -> None:
    audit_file = tmp_path / "audit_history.jsonl"
    audit_file.write_text(
        "".join(json.dumps({"id": index}) + "\n" for index in range(2000)),
        encoding="utf-8",
    )
    monkey_patch = patch.object(Path, "read_text", side_effect=AssertionError("full-file read is forbidden"))
    monkey_patch.start()
    try:
        audit_module._AUDIT_READ_BLOCK_SIZE = 64
        result = _records(AuditRepository(tmp_path).get_audit_log(limit=3))
    finally:
        monkey_patch.stop()
        audit_module._AUDIT_READ_BLOCK_SIZE = 64 * 1024

    assert result == [{"id": 1997}, {"id": 1998}, {"id": 1999}]
