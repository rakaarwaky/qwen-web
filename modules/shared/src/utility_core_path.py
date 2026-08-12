"""Path-algebra and file-state pure utilities.

Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import DEFAULT_TODO

SKIP_DIRS = {"done", "failed", ".processing", "proc"}


def resolve_role_paths(rel_path: Path, cfg: AppConfig) -> tuple[Path, Path, Path, Path]:
    """Resolve role-based paths for output, done, failed, and processing.

    Returns (out_path, done_path, fail_path, proc_file).
    """
    parts = rel_path.parts
    is_single_file_input = cfg.mode == "single" or bool(cfg.input_path.suffix) or cfg.input_path.is_file()
    base = DEFAULT_TODO if is_single_file_input else cfg.input_path

    role_idx = next((i for i, p in enumerate(parts) if p.startswith("role-")), None)
    if role_idx is not None:
        role_folder = parts[role_idx]
        sub_parts = parts[role_idx + 1:]
        if sub_parts and sub_parts[0] in SKIP_DIRS:
            sub_parts = sub_parts[1:]
        sub_path = Path(*sub_parts) if sub_parts else Path(rel_path.name)

        out_path = (
            cfg.output_path / sub_path.name
            if not (cfg.mode == "single" and cfg.output_path.suffix)
            else cfg.output_path
        )
        done_path = base / role_folder / "done" / sub_path
        fail_path = base / role_folder / "failed" / sub_path
        proc_file = cfg.proc_path / role_folder / sub_path
    else:
        sub_parts = parts
        if sub_parts and sub_parts[0] in SKIP_DIRS:
            sub_parts = sub_parts[1:]
        sub_path = Path(*sub_parts) if sub_parts else Path(rel_path.name)

        out_path = (
            cfg.output_path / sub_path.name
            if not (cfg.mode == "single" and cfg.output_path.suffix)
            else cfg.output_path
        )
        done_path = cfg.done_path / sub_path
        fail_path = cfg.failed_path / sub_path
        proc_file = cfg.proc_path / sub_path

    return out_path, done_path, fail_path, proc_file


def should_process_file(f: Path, base_src: Path) -> bool:
    """Check if file qualifies for queue processing."""
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
