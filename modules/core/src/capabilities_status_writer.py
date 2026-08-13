"""Capabilities: JSON status file writer (AES403).

Implements IStatusProtocol — atomic JSON status files for systemd/monitoring tools.
"""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path
from typing import Any

from modules.core.src.utility_core_io_writer import atomic_write_json, ensure_dir
from modules.shared.src.contract_status_protocol import IStatusProtocol
from modules.shared.src.taxonomy_core_vo import StatusRecordVO
from modules.shared.src.utility_core_status import status_path_for


# Block 1: Class Definition & Constructor ──────────────
class StatusFileWriter(IStatusProtocol):
    """Writes JSON status file for systemd/monitoring tools."""

    def __init__(self, status_path: Path) -> None:

        self._status_path = status_path
        ensure_dir(self._status_path)

    # ─── Block 2: Public Contract (IStatusProtocol ONLY) ──
    def write(self, **kwargs: Any) -> None:
        """Atomically write status to disk."""
        rec: dict[str, Any] = {
            "status": kwargs.get("status", "unknown"),
            "mode": kwargs.get("mode", "unknown"),
            "headless": kwargs.get("headless", False),
            "run_id": kwargs.get("run_id"),
            "files_processed": kwargs.get("files_processed", 0),
            "files_failed": kwargs.get("files_failed", 0),
        }
        if kwargs.get("cpu_sec") is not None:
            rec["cpu_sec"] = round(kwargs["cpu_sec"], 2)
        if kwargs.get("error"):
            rec["error"] = kwargs["error"]

        with suppress(OSError):
            atomic_write_json(self._status_path, rec)

    def write_record(self, record: StatusRecordVO) -> None:
        """Atomically write a StatusRecordVO to disk."""
        self.write(
            status=record.status,
            mode=record.mode,
            headless=record.headless,
            run_id=record.run_id,
            error=record.error,
            cpu_sec=record.cpu_sec,
            files_processed=record.files_processed,
            files_failed=record.files_failed,
        )

    def read(self) -> dict[str, Any] | None:
        try:
            result: Any = json.loads(self._status_path.read_text(encoding="utf-8"))
            return result if isinstance(result, dict) else None
        except FileNotFoundError:
            return None
        except Exception:
            return None

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────
    def __repr__(self) -> str:
        return "StatusFileWriter()"

    @classmethod
    def create_default(cls, log_path: Path) -> StatusFileWriter:
        return cls(status_path_for(log_path))


# Module-level convenience function
def get_status_writer(log_path: Path) -> StatusFileWriter:
    """Create a status writer at log_path/status.json (module-level convenience)."""
    return StatusFileWriter(status_path_for(log_path))
