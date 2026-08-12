"""Unit tests for enterprise saver module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.core.src.capabilities_output_saver import write_output
from modules.shared.src import OutputWriteError, RunContext, SaverConfig


def test_write_output_success(tmp_path: Path):
    out_file = tmp_path / "result.md"
    ctx = RunContext()

    write_output(
        path=out_file,
        content="This is the AI response.",
        ctx=ctx,
        src="input.md",
        dur=1.23,
        input_chars=10,
        output_chars=23,
    )

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "METADATA TRACEABILITY" in content
    assert ctx.run_id in content
    assert "This is the AI response." in content

    sidecar = out_file.with_suffix(".meta.json")
    assert sidecar.exists()
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    assert meta["run_id"] == ctx.run_id
    assert meta["source_file"] == "input.md"
    assert meta["duration_sec"] == 1.23


def test_write_output_no_header_no_sidecar(tmp_path: Path):
    out_file = tmp_path / "plain.md"
    ctx = RunContext()
    cfg = SaverConfig(include_header=False, generate_sidecar=False)

    write_output(
        path=out_file,
        content="Plain content",
        ctx=ctx,
        src="plain_input.md",
        dur=0.5,
        input_chars=5,
        output_chars=13,
        config=cfg,
    )

    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == "Plain content"
    assert not out_file.with_suffix(".meta.json").exists()


def test_write_output_invalid_dir(tmp_path: Path):
    # Pass a path where parent is a file (unwriteable directory)
    file_as_dir = tmp_path / "blocked"
    file_as_dir.write_text("i am a file")
    out_file = file_as_dir / "child.md"

    ctx = RunContext()
    with pytest.raises(OutputWriteError, match="Failed to write output file"):
        write_output(
            path=out_file,
            content="test",
            ctx=ctx,
            src="test.md",
            dur=0.1,
            input_chars=4,
            output_chars=4,
        )
