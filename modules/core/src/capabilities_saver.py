"""Capabilities: file saver (AES403).

Implements ISaverProtocol.
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.shared.src.contract_core_protocol import ISaverProtocol
from modules.shared.src.taxonomy_core_vo import (
    AtomicWriteFlag,
    GenerateSidecarFlag,
    IncludeHeaderFlag,
    RunContext,
)
from modules.shared.src.taxonomy_domain_error import OutputWriteError

log = __import__("logging").getLogger("capabilities_saver")

DEFAULT_INCLUDE_HEADER = IncludeHeaderFlag(True)
DEFAULT_GENERATE_SIDECAR = GenerateSidecarFlag(True)
DEFAULT_ATOMIC_WRITE = AtomicWriteFlag(True)


def _strip_ui_noise(text: str) -> str:
    """Remove Qwen UI chrome from the start of captured output."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in ("?", "Qwen3", "Qwen3.8-Max", "Qwen Plus", "Qwen Max",
                        "Qwen Turbo", "Auto"):
            continue
        if stripped.endswith((".md", " KB", " B")):
            continue
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
            with contextlib.suppress(OSError):
                tmp_path.unlink()
        raise OutputWriteError(f"Failed to write output file {target_path}: {e}") from e


class Saver(ISaverProtocol):
    """Atomic file writer with metadata traceability header and JSON sidecar."""

    def __init__(
        self,
        include_header: IncludeHeaderFlag = DEFAULT_INCLUDE_HEADER,
        generate_sidecar: GenerateSidecarFlag = DEFAULT_GENERATE_SIDECAR,
        atomic_write: AtomicWriteFlag = DEFAULT_ATOMIC_WRITE,
    ) -> None:
        self.include_header = include_header
        self.generate_sidecar = generate_sidecar
        self.atomic_write = atomic_write

    def write_output(
        self,
        path: Path,
        content: str,
        ctx: RunContext,
        src: str,
        dur: float,
        input_chars: int,
        output_chars: int,
        config: Any | None = None,
    ) -> None:
        """Write processed output to disk with metadata traceability header."""
        cfg = config or {}
        include_header = cfg.get("include_header", self.include_header)
        generate_sidecar = cfg.get("generate_sidecar", self.generate_sidecar)
        atomic_write = cfg.get("atomic_write", self.atomic_write)
        run_id = str(ctx.run_id)

        processed_at = datetime.now(tz=timezone.utc)
        iso_timestamp = processed_at.isoformat()

        header = ""
        if include_header:
            header = (
                "<!--\n"
                "--- METADATA TRACEABILITY ---\n"
                f"Run ID           : {run_id}\n"
                f"Source File      : {src}\n"
                f"Processed At     : {iso_timestamp}\n"
                f"Duration         : {dur:.2f}s\n"
                f"Input Characters : {input_chars}\n"
                f"Output Characters: {output_chars}\n"
                "------------------------------\n"
                "-->\n\n"
            )

        full_text = header + _strip_ui_noise(content)

        if atomic_write:
            _write_file_atomic(path, full_text)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                path.write_text(full_text, encoding="utf-8")
            except OSError as e:
                log.error("Failed to write output file %s (I/O error): %s", path, e)
                raise OutputWriteError(f"Failed to write output file {path}: {e}") from e

        if generate_sidecar:
            sidecar_path = path.with_suffix(".meta.json")
            try:
                meta_dict = {
                    "run_id": run_id,
                    "source_file": src,
                    "processed_at": iso_timestamp,
                    "duration_sec": round(dur, 2),
                    "input_chars": input_chars,
                    "output_chars": output_chars,
                }
                if self.atomic_write:
                    _write_file_atomic(sidecar_path, json.dumps(meta_dict, ensure_ascii=False) + "\n")
                else:
                    sidecar_path.write_text(
                        json.dumps(meta_dict, ensure_ascii=False) + "\n", encoding="utf-8"
                    )
            except Exception as e:
                log.error("Failed to write metadata sidecar for %s: %s", path, e)

        log.info("output_file_written: %s", path.name)


# Module-level convenience function
def write_output(
    path: Path,
    content: str,
    ctx: RunContext,
    src: str,
    dur: float,
    input_chars: int,
    output_chars: int,
    config: Any | None = None,
) -> None:
    """Write output file (module-level convenience)."""
    saver = Saver()
    saver.write_output(path, content, ctx, src, dur, input_chars, output_chars, config)
