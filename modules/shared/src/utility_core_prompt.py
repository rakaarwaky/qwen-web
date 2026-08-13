"""Prompt-handling pure utilities.

Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.taxonomy_core_constant import DEFAULT_TODO


def extract_prompt_text(content: str) -> str:
    """Strip YAML frontmatter header if present."""
    stripped = content.strip()
    if stripped.startswith("---"):
        parts = stripped.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return stripped


def get_role_search_directories(file_path: Path, rel_path: Path | None) -> list[Path]:
    """Collect priority list of directories to search for PROMPT.md."""
    search_dirs: list[Path] = []

    if rel_path and rel_path.parts and rel_path.parts[0].startswith("role-"):
        role_dir_rel = DEFAULT_TODO / rel_path.parts[0]
        search_dirs.extend([role_dir_rel, role_dir_rel.resolve()])

    abs_path = file_path.resolve()
    curr_abs = abs_path.parent if abs_path.is_file() else abs_path
    search_dirs.append(curr_abs)
    search_dirs.extend(curr_abs.parents)

    curr_rel = file_path.parent if file_path.is_file() else file_path
    if curr_rel not in search_dirs:
        search_dirs.append(curr_rel)
        search_dirs.extend(curr_rel.parents)

    for path_obj in (abs_path, file_path):
        for part in path_obj.parts:
            if part.startswith("role-"):
                search_dirs.extend([DEFAULT_TODO.resolve() / part, DEFAULT_TODO / part])

    return search_dirs


def load_role_prompt(
    file_path: Path,
    custom_prompt_path: Path | None = None,
    rel_path: Path | None = None,
) -> str:
    """Dynamically loads custom PROMPT.md from file's parent role directory in input/."""
    if custom_prompt_path and custom_prompt_path.exists() and custom_prompt_path.is_file():
        return extract_prompt_text(custom_prompt_path.read_text(encoding="utf-8"))

    for p in get_role_search_directories(file_path, rel_path):
        prompt_file = p / "PROMPT.md"
        if prompt_file.exists() and prompt_file.is_file():
            content = extract_prompt_text(prompt_file.read_text(encoding="utf-8"))
            if content:
                return content
    return ""


def strip_input_from_output(text: str, full_prompt: str) -> str:
    """Strip leaked input content from AI response."""
    if not text or not full_prompt:
        return text

    prompt_stripped = full_prompt.strip()
    text_stripped = text.strip()

    if text_stripped.startswith(prompt_stripped):
        candidate = text_stripped[len(prompt_stripped) :].lstrip("\n")
        if len(candidate.strip()) > 20:
            return candidate

    lines = text_stripped.splitlines()
    prompt_lines = set(prompt_stripped.splitlines())
    if prompt_lines and len(prompt_lines) > 5:
        matching = sum(1 for line in lines if line.strip() in prompt_lines)
        if matching >= len(prompt_lines) * 0.8 and matching > 3:
            filtered = [line for line in lines if line.strip() not in prompt_lines]
            result = "\n".join(filtered).strip()
            if len(result) > 20:
                return result

    return text
