"""File mover utilities.

Utility layer (utility_core_file_mover): stateless functions for file movement.
Consumed by Agent orchestrator for proc/done/failed file routing.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from modules.core.src.utility_core_io_writer import ensure_dir


def move_file(source: Path, destination: Path) -> None:
    """Move a file from source to destination.

    Parameters
    ----------
    source : Path
        Source file path.
    destination : Path
        Destination file path (parent must exist).

    """
    shutil.move(str(source), str(destination))


def move_to_processing(source: Path, proc_dest: Path) -> None:
    """Move a file into the processing directory.

    Creates the parent directory if needed.

    Parameters
    ----------
    source : Path
        Source file path (e.g. from input/todo).
    proc_dest : Path
        Target path inside the .processing directory.

    """
    ensure_dir(proc_dest)
    shutil.move(str(source), str(proc_dest))
