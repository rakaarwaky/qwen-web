"""Filesystem writer utilities.

Utility layer (utility_core_io_writer): atomic file writing and JSONL append.
Stateless functions consumed by Saver, StatusFileWriter, AuditRepository.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def atomic_write_text(target: Path, data: str) -> None:
    """Atomically write text to a file via temp + rename.

    Parameters
    ----------
    target : Path
        Destination file path.
    data : str
        Text content to write.

    """
    tmp_path = target.with_suffix(".tmp")
    tmp_path.write_text(data, encoding="utf-8")
    try:
        tmp_path.rename(target)
    except OSError:
        pass


def atomic_write_json(target: Path, payload: Mapping[str, Any]) -> None:
    """Atomically write JSON to a file via temp + rename.

    Parameters
    ----------
    target : Path
        Destination file path.
    payload : Mapping[str, Any]
        Dict-like object to serialize as JSON.

    """
    tmp_path = target.with_suffix(".tmp")
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp_path.rename(target)
    except OSError:
        pass


def append_jsonl(target: Path, record: Mapping[str, Any]) -> None:
    """Append a single JSON object to a JSONL file.

    Parameters
    ----------
    target : Path
        Destination JSONL file path.
    record : Mapping[str, Any]
        Dict-like object to serialize as one JSON line.

    """
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
