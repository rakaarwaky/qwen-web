"""Output file writing with metadata traceability header."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .types import RunContext
from .observability import get_logger

log = get_logger("saver")


def write_output(path: Path, content: str, ctx: RunContext, src: str, dur: float, in_c: int, out_c: int) -> None:
    """Writes processed output to disk with metadata traceability header."""
    header = (
        "<!--\n"
        "--- METADATA TRACEABILITY ---\n"
        f"Run ID           : {ctx.run_id}\n"
        f"Source File      : {src}\n"
        f"Processed At     : {datetime.now().isoformat()}\n"
        f"Duration         : {dur:.2f}s\n"
        f"Input Characters : {in_c}\n"
        f"Output Characters: {out_c}\n"
        "-----------------------------\n"
        "-->\n\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + content, encoding="utf-8")

    sidecar_path = path.with_suffix(".meta.json")
    try:
        meta = {
            "run_id": ctx.run_id,
            "source_file": src,
            "processed_at": datetime.now().isoformat(),
            "duration_sec": round(dur, 2),
            "input_chars": in_c,
            "output_chars": out_c,
        }
        sidecar_path.write_text(json.dumps(meta, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass

    log.info("output_file_copied", filename=path.name)
