"""Output file writing with metadata traceability header."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .types import RunContext
from .observability import get_logger

log = get_logger("saver")


def write_output(
    path: Path,
    content: str,
    ctx: RunContext,
    src: str,
    dur: float,
    input_chars: int,
    output_chars: int,
) -> None:
    """Writes processed output to disk with metadata traceability header and JSON sidecar."""
    processed_at = datetime.now()
    iso_timestamp = processed_at.isoformat()

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
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(header + content, encoding="utf-8")
    except OSError as e:
        log.error("Failed to write output file %s (I/O error): %s", path, e)
        raise

    sidecar_path = path.with_suffix(".meta.json")
    try:
        meta = {
            "run_id": ctx.run_id,
            "source_file": src,
            "processed_at": iso_timestamp,
            "duration_sec": round(dur, 2),
            "input_chars": input_chars,
            "output_chars": output_chars,
        }
        sidecar_path.write_text(json.dumps(meta, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as e:
        log.error("Failed to write metadata sidecar (I/O): %s", e)
    except (TypeError, ValueError) as e:
        log.error("Failed to serialize metadata: %s", e)

    log.info("output_file_written", filename=path.name)
