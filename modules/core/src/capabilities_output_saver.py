"""Capabilities: file saver (AES403).

Implements ISaverProtocol.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from modules.core.src.utility_core_io_writer import atomic_write_text, ensure_dir, write_json_file
from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src.contract_core_protocol import ISaverProtocol
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_ATOMIC_WRITE,
    DEFAULT_GENERATE_SIDECAR,
    DEFAULT_INCLUDE_HEADER,
)
from modules.shared.src.taxonomy_core_vo import (
    AtomicWriteFlag,
    GenerateSidecarFlag,
    IncludeHeaderFlag,
    RunContext,
)
from modules.shared.src.taxonomy_domain_error import OutputWriteError
from modules.shared.src.utility_core_text import build_metadata_header, strip_ui_noise, utc_now_iso

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

        # Hoist mkdir before conditional branches (deduplication)
        try:
            ensure_dir(path)
        except OSError as e:
            log.error("Failed to create parent dirs for %s (I/O error): %s", path, e)
            raise OutputWriteError(f"Failed to write output file {path}: {e}") from e
        self._write_text_file(path, full_text, atomic_write)

        if generate_sidecar:
            sidecar_path = path.with_suffix(".meta.json")
            ensure_dir(sidecar_path)
            try:
                meta_dict = {
                    "run_id": run_id,
                    "source_file": src,
                    "processed_at": iso_timestamp,
                    "duration_sec": round(dur, 2),
                    "input_chars": input_chars,
                    "output_chars": output_chars,
                }
                write_json_file(sidecar_path, meta_dict, atomic=bool(atomic_write))
            except (OSError, TypeError, ValueError) as e:
                log.error("Failed to write metadata sidecar for %s: %s", path, e)

        log.info("output_file_written: %s", path.name)

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def _write_text_file(self, path: Path, content: str, atomic: bool) -> None:
        """Write *content* to *path*, atomically or directly.

        Raises
        ------
        OutputWriteError
            When an I/O error occurs on the non-atomic write path.
        """
        if atomic:
            atomic_write_text(path, content)
            return
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as e:
            log.error("Failed to write output file %s (I/O error): %s", path, e)
            raise OutputWriteError(f"Failed to write output file {path}: {e}") from e

    def __repr__(self) -> str:
        """Return string representation of Saver."""
        return f"Saver(header={self.include_header}, sidecar={self.generate_sidecar}, atomic={self.atomic_write})"
