"""Utility: path resolution and file algebra (AES404)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from ..common.taxonomy_core_constant import DEFAULT_TODO, DEFAULT_PROC, DEFAULT_OUTPUT


def resolve_role_paths(
    rel_path: Path,
    cfg_input_path: Path,
    cfg_output_path: Path,
    cfg_done_path: Path,
    cfg_failed_path: Path,
    cfg_proc_path: Path,
) -> tuple[Path, Path, Path, Path]:
    """Resolve role-based paths for output, done, failed, and processing.

    Returns (out_path, done_path, fail_path, proc_file).
    """
    parts = rel_path.parts
    is_single_file_input = cfg_input_path.is_file()

    base = DEFAULT_TODO if is_single_file_input else cfg_input_path

    # Check if role-* exists in parts
    role_idx = next((i for i, p in enumerate(parts) if p.startswith("role-")), None)
    if role_idx is not None:
        role_folder = parts[role_idx]
        sub_parts = parts[role_idx + 1 :]
        if sub_parts and sub_parts[0] in ("todo", "done", "failed", ".processing", "proc"):
            sub_parts = sub_parts[1:]
        sub_path = Path(*sub_parts) if sub_parts else Path(rel_path.name)

        out_path = (
            cfg_output_path / sub_path.name
            if not (is_single_file_input and str(cfg_output_path).endswith(".md"))
            else cfg_output_path
        )
        done_path = base / role_folder / "done" / sub_path
        fail_path = base / role_folder / "failed" / sub_path
        proc_file = cfg_proc_path / role_folder / sub_path
    else:
        sub_parts = parts
        if sub_parts and sub_parts[0] in ("todo", "done", "failed", ".processing", "proc"):
            sub_parts = sub_parts[1:]
        sub_path = Path(*sub_parts) if sub_parts else Path(rel_path.name)

        out_path = (
            cfg_output_path / sub_path.name
            if not (is_single_file_input and str(cfg_output_path).endswith(".md"))
            else cfg_output_path
        )
        done_path = cfg_done_path / sub_path
        fail_path = cfg_failed_path / sub_path
        proc_file = cfg_proc_path / sub_path

    return out_path, done_path, fail_path, proc_file


def should_process_file(f: Path, base_src: Path) -> bool:
    """Check if file qualifies for queue processing."""
    SKIP_DIRS = {"done", "failed", ".processing", "proc"}

    if not f.is_file() or f.name.startswith(".") or f.name.upper() == "PROMPT.MD":
        return False
    try:
        rel_parts = f.resolve().relative_to(base_src.resolve()).parts
    except ValueError:
        return False

    if len(rel_parts) < 2 or not rel_parts[0].startswith("role-"):
        return False
    return not any(p in SKIP_DIRS or p.startswith(".") for p in rel_parts[:-1])


def list_input_files(base_path: Path) -> list[tuple[Path, Path]]:
    """List input files from base_path, excluding PROMPT.md and internal folders."""
    if not base_path.is_dir():
        return []
    return [
        (f, f.resolve().relative_to(base_path.resolve()))
        for f in sorted(f for f in base_path.rglob("*") if should_process_file(f, base_path))
    ]


def cleanup_empty_dirs(dir_path: Path, root_limit: Path) -> None:
    """Remove empty parent directories up to root_limit."""
    try:
        curr = dir_path
        root_res = root_limit.resolve()
        while curr.exists() and curr.resolve() != root_res and root_res in curr.resolve().parents:
            if not any(curr.iterdir()):
                curr.rmdir()
                curr = curr.parent
            else:
                break
    except Exception:
        pass


def move_file_to_proc(src: Path, rel_path: Path, proc_path: Path) -> Path:
    """Move a file to processing directory and return the new path."""
    proc_file = proc_path / rel_path
    proc_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(proc_file))
    return proc_file


def move_file_to_done(proc_file: Path, done_path: Path, rel_path: Path) -> None:
    """Move processed file to done directory."""
    if proc_file.resolve() != done_path.resolve():
        try:
            proc_file.unlink()
        except Exception:
            pass
    else:
        done_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(proc_file), str(done_path))


def move_file_to_failed(proc_file: Path, fail_path: Path, rel_path: Path) -> None:
    """Move failed file to failed directory."""
    if proc_file.exists():
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(proc_file), str(fail_path))
    else:
        try:
            proc_file.unlink()
        except Exception:
            pass