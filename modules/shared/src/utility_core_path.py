"""
Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.taxonomy_core_vo import AppConfig

SKIP_DIRS: frozenset[str] = frozenset({"done", "failed", ".processing", "proc"})
ROLE_PATH_SKIP_DIRS: frozenset[str] = frozenset({"todo", "done", "failed", ".processing", "proc"})


def _normalize_sub_parts(parts: tuple[str, ...], fallback_name: str) -> Path:
    """Strip leading skip dirs and rebuild the sub-path, falling back to the file name."""
    sub_parts = parts
    if sub_parts and sub_parts[0] in ROLE_PATH_SKIP_DIRS:
        sub_parts = sub_parts[1:]
    return Path(*sub_parts) if sub_parts else Path(fallback_name)


def _compute_output_path(cfg: AppConfig, sub_path: Path) -> Path:
    """Resolve the output destination for a sub-path (single-file target or directory join)."""
    if cfg.mode == "single" and cfg.output_path.suffix:
        return cfg.output_path
    return cfg.output_path / sub_path.name





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
    return not any(part in SKIP_DIRS or part.startswith(".") for part in rel_parts[:-1])


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
    except (OSError, PermissionError):
        pass
