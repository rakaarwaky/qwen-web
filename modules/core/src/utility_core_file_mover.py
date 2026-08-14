"""
Utility layer (utility_core_file_mover): stateless functions for file movement.
Consumed by Agent orchestrator for proc/done/failed file routing.
"""

from __future__ import annotations

import errno
import os
import shutil
import tempfile
from pathlib import Path


def _fsync_directory(directory: Path) -> None:
    """Flush directory metadata when the platform supports directory fsync."""
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _copy_then_replace(source: Path, destination: Path) -> None:
    """Copy a source to a destination-side temp file before committing it."""
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            with source.open("rb") as source_file:
                shutil.copyfileobj(source_file, temp_file)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        shutil.copystat(source, temp_path)
        with temp_path.open("rb") as copied_file:
            os.fsync(copied_file.fileno())
        os.replace(temp_path, destination)
        _fsync_directory(destination.parent)
        source.unlink()
        _fsync_directory(source.parent)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def move_file(source: Path, destination: Path) -> None:
    """Move a file atomically whenever possible.

    Same-device moves use ``os.replace``.  When the source and destination are
    on different devices, the function copies to a temporary file located next
    to the destination, fsyncs it, atomically replaces the destination, and
    only then unlinks the source.  A failed copy never removes the source or
    exposes a partial destination.
    """
    source = Path(source)
    destination = Path(destination)
    if source.resolve() == destination.resolve():
        return
    if not source.is_file():
        raise FileNotFoundError(source)

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(source, destination)
        _fsync_directory(destination.parent)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        _copy_then_replace(source, destination)


def move_to_processing(source: Path, proc_dest: Path) -> None:
    """Move a queue file into the processing directory atomically."""
    move_file(source, proc_dest)
