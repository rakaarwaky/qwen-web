"""Text-formatting pure utilities: UI-noise stripping and metadata header.

Taxonomy layer (utility): stateless functions, taxonomy imports only.
"""

from __future__ import annotations

from datetime import datetime, timezone

from modules.shared.src.taxonomy_core_vo import RunContext

UI_NOISE_TOKENS = (
    "?",
    "Qwen3",
    "Qwen3.8-Max",
    "Qwen Plus",
    "Qwen Max",
    "Qwen Turbo",
    "Auto",
)


def utc_now_iso() -> str:
    """Return current UTC time as an ISO-format string."""
    return datetime.now(tz=timezone.utc).isoformat()


def strip_ui_noise(text: str) -> str:
    """Remove Qwen UI chrome from the start of captured output."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in UI_NOISE_TOKENS:
            continue
        if stripped.endswith((".md", " KB", " B")):
            continue
        return "\n".join(lines[i:])
    return text


def build_metadata_header(
    ctx: RunContext,
    src: str,
    dur: float,
    input_chars: int,
    output_chars: int,
) -> str:
    """Build the METADATA TRACEABILITY header block for saved output."""
    iso_timestamp = utc_now_iso()
    return (
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
