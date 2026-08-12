"""Utility: stateless prompt text handling (AES404)."""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("utility_core_prompt")


def load_role_prompt(
    file_path: Path,
    custom_prompt_path: Path | None = None,
    rel_path: Path | None = None,
) -> str:
    """Dynamically loads custom PROMPT.md from file's parent role directory in input/.

    Args:
        file_path: Path to the prompt file being processed.
        custom_prompt_path: Optional custom prompt file path.
        rel_path: Optional relative path for role detection.

    Returns:
        Role prompt text (YAML frontmatter stripped), or empty string if not found.
    """
    if custom_prompt_path and custom_prompt_path.exists() and custom_prompt_path.is_file():
        return _extract_prompt_text(custom_prompt_path.read_text(encoding="utf-8"))

    for p in _get_role_search_directories(file_path, rel_path):
        prompt_file = p / "PROMPT.md"
        if prompt_file.exists() and prompt_file.is_file():
            content = _extract_prompt_text(prompt_file.read_text(encoding="utf-8"))
            if content:
                log.info("Loaded role prompt from %s (%d chars)", prompt_file, len(content))
                return content
    return ""


def _extract_prompt_text(content: str) -> str:
    """Strip YAML frontmatter header if present."""
    stripped = content.strip()
    if stripped.startswith("---"):
        parts = stripped.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return stripped


def _get_role_search_directories(file_path: Path, rel_path: Path | None) -> list[Path]:
    """Collect priority list of directories to search for PROMPT.md."""
    from ..common.taxonomy_core_constant import DEFAULT_TODO

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


def strip_input_from_output(text: str, full_prompt: str) -> str:
    """Strip leaked input content from AI response.

    When DOM scraping returns user input mixed with AI response,
    this strips the prompt prefix to return only the AI's output.
    """
    if not text or not full_prompt:
        return text

    prompt_stripped = full_prompt.strip()
    text_stripped = text.strip()

    if text_stripped.startswith(prompt_stripped):
        candidate = text_stripped[len(prompt_stripped) :].lstrip("\n")
        if len(candidate.strip()) > 20:
            log.info("Stripped %d chars of leaked input from response", len(prompt_stripped))
            return candidate

    lines = text_stripped.splitlines()
    prompt_lines = set(prompt_stripped.splitlines())
    if prompt_lines and len(prompt_lines) > 5:
        matching = sum(1 for l in lines if l.strip() in prompt_lines)
        if matching >= len(prompt_lines) * 0.8 and matching > 3:
            filtered = [l for l in lines if l.strip() not in prompt_lines]
            result = "\n".join(filtered).strip()
            if len(result) > 20:
                log.info("Filtered %d matching prompt lines from response", matching)
                return result

    return text