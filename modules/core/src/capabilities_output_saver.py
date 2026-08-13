"""Capabilities: file saver (AES403).

Implements ISaverProtocol.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from modules.shared.src.contract_core_protocol import ISaverProtocol
from modules.shared.src.taxonomy_core_vo import (
    AtomicWriteFlag,
    GenerateSidecarFlag,
    IncludeHeaderFlag,
    RunContext,
)
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_ATOMIC_WRITE,
    DEFAULT_GENERATE_SIDECAR,
    DEFAULT_INCLUDE_HEADER,
)
from modules.shared.src.taxonomy_domain_error import OutputWriteError
from modules.core.src.utility_core_io_writer import atomic_write_text
from modules.shared.src.utility_core_text import build_metadata_header, strip_ui_noise
from modules.core.src.utility_core_time_formatter import utc_now_iso
from modules.core.src.utility_core_logger_factory import get_logger

log = get_logger("capabilities_saver")



# Block 1: Class Definition & Constructor


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

    # ─── Block 2: Public Contract (ISaverProtocol ONLY) ──
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
        # Support both plain dict and dataclass-style config objects
        if not isinstance(cfg, dict):
            cfg = {
                "include_header": getattr(cfg, "include_header", self.include_header),
                "generate_sidecar": getattr(cfg, "generate_sidecar", self.generate_sidecar),
                "atomic_write": getattr(cfg, "atomic_write", self.atomic_write),
            }
        include_header = cfg.get("include_header", self.include_header)
        generate_sidecar = cfg.get("generate_sidecar", self.generate_sidecar)
        atomic_write = cfg.get("atomic_write", self.atomic_write)
        run_id = str(ctx.run_id)

        iso_timestamp = utc_now_iso()

        header = build_metadata_header(ctx, src, dur, input_chars, output_chars) if include_header else ""

        full_text = header + strip_ui_noise(content)

        if atomic_write:
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(path, full_text)
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
                if atomic_write:
                    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
                    atomic_write_text(sidecar_path, json.dumps(meta_dict, ensure_ascii=False) + "\n")
                else:
                    sidecar_path.write_text(
                        json.dumps(meta_dict, ensure_ascii=False) + "\n", encoding="utf-8"
                    )
            except Exception as e:
                log.error("Failed to write metadata sidecar for %s: %s", path, e)

        log.info("output_file_written: %s", path.name)

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def __repr__(self) -> str:
        """Return string representation of Saver."""
        return f"Saver(header={self.include_header}, sidecar={self.generate_sidecar}, atomic={self.atomic_write})"


