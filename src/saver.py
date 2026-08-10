"""Enterprise-grade output file saver module with metadata sidecar support.

Provides atomic file writing, metadata traceability headers, JSON sidecar generation, and structured exception handling.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .observability import get_logger
from .types import (
    DEFAULT_SAVER_CONFIG,
    OutputMetadata,
    OutputWriteError,
    RunContext,
    SaverConfig,
)

log = get_logger("saver")


def _strip_ui_noise(text: str) -> str:
    """Remove Qwen UI chrome from the start of captured output.

    When JS scrapes the live DOM, short UI strings (model name, file card,
    placeholder) may appear before the actual AI response.  This trims
    everything before the first line that looks like real content:
    a markdown heading, a list item, a sentence, or a code fence.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip blank lines and known Qwen UI noise tokens
        if not stripped:
            continue
        if stripped in ("?", "Qwen3", "Qwen3.8-Max", "Qwen Plus", "Qwen Max",
                        "Qwen Turbo", "Auto"):
            continue
        if stripped.endswith(".md") or stripped.endswith(" KB") or stripped.endswith(" B"):
            continue
        # First meaningful line found — return from here onwards
        return "\n".join(lines[i:])
    return text


def _write_file_atomic(target_path: Path, data: str) -> None:
    """Atomically write text content to target path using a temporary file."""
    tmp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(data, encoding="utf-8")
        tmp_path.replace(target_path)
    except OSError as e:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise OutputWriteError(f"Failed to write output file {target_path}: {e}") from e


def write_output(
    path: Path,
    content: str,
    ctx: RunContext,
    src: str,
    dur: float,
    input_chars: int,
    output_chars: int,
    config: SaverConfig | None = None,
) -> None:
    """Write processed output to disk with metadata traceability header and JSON sidecar.

    Args:
        path: Destination file path.
        content: Main body text content.
        ctx: Active RunContext containing execution run_id.
        src: Source filename or path string.
        dur: Total processing duration in seconds.
        input_chars: Character count of prompt input.
        output_chars: Character count of AI response output.
        config: Optional SaverConfig instance.

    Raises:
        OutputWriteError: If primary file write operation fails.

    """
    cfg = config or DEFAULT_SAVER_CONFIG
    processed_at = datetime.now()
    iso_timestamp = processed_at.isoformat()

    header = ""
    if cfg.include_header:
        header = (
            "<!--\n"
            "--- METADATA TRACEABILITY ---\n"
            f"Run ID           : {ctx.run_id}\n"
            f"Source File      : {src}\n"
            f"Processed At     : {iso_timestamp}\n"
            f"Duration         : {dur:.2f}s\n"
            f"Input Characters : {input_chars}\n"
            f"Output Characters: {output_chars}\n"
            "-----------------------------\n"
            "-->\n\n"
        )

    full_text = header + _strip_ui_noise(content)

    if cfg.atomic_write:
        _write_file_atomic(path, full_text)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text(full_text, encoding="utf-8")
        except OSError as e:
            log.error("Failed to write output file %s (I/O error): %s", path, e)
            raise OutputWriteError(f"Failed to write output file {path}: {e}") from e

    if cfg.generate_sidecar:
        sidecar_path = path.with_suffix(".meta.json")
        try:
            meta = OutputMetadata(
                run_id=ctx.run_id,
                source_file=src,
                processed_at=iso_timestamp,
                duration_sec=round(dur, 2),
                input_chars=input_chars,
                output_chars=output_chars,
            )
            meta_dict = {
                "run_id": meta.run_id,
                "source_file": meta.source_file,
                "processed_at": meta.processed_at,
                "duration_sec": meta.duration_sec,
                "input_chars": meta.input_chars,
                "output_chars": meta.output_chars,
            }
            if cfg.atomic_write:
                _write_file_atomic(sidecar_path, json.dumps(meta_dict, ensure_ascii=False) + "\n")
            else:
                sidecar_path.write_text(
                    json.dumps(meta_dict, ensure_ascii=False) + "\n", encoding="utf-8"
                )
        except Exception as e:
            log.error("Failed to write metadata sidecar for %s: %s", path, e)

    log.info("output_file_written", filename=path.name)
