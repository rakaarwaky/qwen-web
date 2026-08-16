"""Filesystem writer utilities.

Utility layer (utility_core_io_writer): atomic file writing, JSONL append,
and directory creation helpers. Stateless functions consumed by Saver
and StatusFileWriter.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any

from modules.shared.src.taxonomy_core_error import OutputWriteError


def _atomic_write(target: Path, content: str) -> None:
    """Write content to a file atomically via temp + replace.

    Parameters
    ----------
    target : Path
        Destination file path.
    content : str
        Text content to write.

    """
    tmp_path = target.with_suffix(f".tmp_{target.name}")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(target)
    except OSError as err:
        if tmp_path.exists():
            with suppress(OSError):
                tmp_path.unlink()
        raise OutputWriteError(f"Atomic write failed for {target}: {err}") from err


def atomic_write_text(target: Path, data: str) -> None:
    """Atomically write text to a file via temp + rename.

    Parameters
    ----------
    target : Path
        Destination file path.
    data : str
        Text content to write.

    """
    _atomic_write(target, data)


def atomic_write_json(target: Path, payload: Mapping[str, Any]) -> None:
    """Atomically write JSON to a file via temp + rename.

    Parameters
    ----------
    target : Path
        Destination file path.
    payload : Mapping[str, Any]
        Dict-like object to serialize as JSON.

    """
    _atomic_write(target, json.dumps(payload, ensure_ascii=False) + "\n")


def write_json_file(target: Path, payload: Mapping[str, Any], atomic: bool = True) -> None:
    """Write JSON to file, atomically or directly.

    Parameters
    ----------
    target : Path
        Destination file path.
    payload : Mapping[str, Any]
        Dict-like object to serialize as JSON.
    atomic : bool
        If True, use atomic write (temp + rename). If False, write directly.
    """
    content = json.dumps(payload, ensure_ascii=False) + "\n"
    if atomic:
        _atomic_write(target, content)
    else:
        target.write_text(content, encoding="utf-8")


def ensure_dir(path: Path) -> Path:
    """Create parent directories for *path* if they do not exist.

    Returns *path* so it can be used in expressions.  Equivalent to
    ``path.parent.mkdir(parents=True, exist_ok=True)`` but centralised
    and reusable across the codebase.

    Parameters
    ----------
    path : Path
        File path whose parent directory will be ensured.

    Returns
    -------
    Path
        The original *path* (unchanged).

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_orchestrator_output(
    saver: Any,
    out_path: Path,
    p_path: Path,
    text: str,
    dur: float,
    ctx: Any,
) -> None:
    """Save output text to file via saver capability."""
    from modules.shared.src.taxonomy_core_vo import FilePath, OutputChars, ResponseText

    prompt_len = p_path.stat().st_size if p_path.exists() else 0
    saver.write_output(
        out_path,
        ResponseText(text),
        ctx,
        FilePath(str(p_path)),
        dur,
        prompt_len,
        OutputChars(len(text)),
    )
