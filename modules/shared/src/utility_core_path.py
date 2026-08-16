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


def _role_destination(
    root: Path, role_folder: str, sub_path: Path, marker: str, input_root: Path | None = None
) -> Path:
    """Join a role below a workspace root without breaking role-local defaults."""
    if root.name == marker and root.parent.name == role_folder:
        return root / sub_path
    if input_root is not None and root.name == marker and root.parent.resolve() == input_root.resolve():
        return root.parent / role_folder / marker / sub_path
    return root / role_folder / sub_path


def resolve_role_paths(rel_path: Path, cfg: AppConfig) -> tuple[Path, Path, Path, Path]:
    """Resolve output, done, failed, and processing paths from one relative path.

    ``rel_path`` may contain a role folder and any queue marker (``todo``,
    ``done``, ``failed``, ``proc`` or ``.processing``).  Configured roots are
    always respected; if a configured root already points at a role directory,
    the role is not appended a second time.
    """
    parts = rel_path.parts
    role_idx = next((i for i, part in enumerate(parts) if part.startswith("role-")), None)

    if role_idx is not None:
        role_folder = parts[role_idx]
        sub_path = _normalize_sub_parts(parts[role_idx + 1 :], rel_path.name)
        out_path = _compute_output_path(cfg, sub_path)
        done_path = _role_destination(cfg.done_path, role_folder, sub_path, "done", cfg.input_path)
        fail_path = _role_destination(cfg.failed_path, role_folder, sub_path, "failed", cfg.input_path)
        proc_file = _role_destination(cfg.proc_path, role_folder, sub_path, ".processing", cfg.input_path)
    else:
        sub_path = _normalize_sub_parts(parts, rel_path.name)
        out_path = _compute_output_path(cfg, sub_path)
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
