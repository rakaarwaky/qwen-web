"""Tests for saver.py — remaining uncovered lines in strip_ui_noise, _write_text_file, write_output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modules.core.src.capabilities_output_saver import Saver
from modules.core.src.utility_core_io_writer import ensure_dir
from modules.shared.src.utility_core_text import strip_ui_noise
from modules.shared.src import OutputWriteError, RunContext, SaverConfig


class TestStripUiNoise:
    def test_strips_qwen_model_names(self):
        text = "Qwen3\nQwen3.8-Max\nActual content here"
        result = strip_ui_noise(text)
        assert "Qwen3" not in result
        assert "Actual content here" in result

    def test_strips_question_mark(self):
        text = "?\nReal answer"
        result = strip_ui_noise(text)
        assert result == "Real answer"

    def test_strips_file_size_suffixes(self):
        text = "12.5 KB\nDocument.docx\nReal content"
        result = strip_ui_noise(text)
        assert "12.5 KB" not in result

    def test_no_stripping_needed(self):
        text = "# Heading\nSome content"
        result = strip_ui_noise(text)
        assert result == text

    def test_all_noise_returns_original(self):
        text = "Qwen3\nQwen Plus\nAuto"
        result = strip_ui_noise(text)
        assert result == text

    def test_blank_lines_before_content(self):
        text = "\n\n\nReal content"
        result = strip_ui_noise(text)
        assert "Real content" in result

    def test_empty_string(self):
        assert strip_ui_noise("") == ""


class TestWriteFileAtomic:
    def test_atomic_write(self, tmp_path):
        target = tmp_path / "output.md"
        Saver()._write_text_file(target, "hello world", atomic=True)
        assert target.read_text() == "hello world"

    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "sub" / "dir" / "file.md"
        ensure_dir(target)
        Saver()._write_text_file(target, "nested", atomic=True)
        assert target.read_text() == "nested"


class TestWriteOutputExtended:
    def test_with_sidecar(self, tmp_path):
        out_file = tmp_path / "result.md"
        ctx = RunContext()
        Saver().write_output(
            path=out_file,
            content="AI answer",
            ctx=ctx,
            src="input.md",
            dur=1.0,
            input_chars=5,
            output_chars=9,
        )
        sidecar = out_file.with_suffix(".meta.json")
        assert sidecar.exists()
        meta = json.loads(sidecar.read_text())
        assert meta["run_id"] == ctx.run_id

    def test_without_sidecar(self, tmp_path):
        out_file = tmp_path / "plain.md"
        ctx = RunContext()
        cfg = SaverConfig(generate_sidecar=False)
        Saver().write_output(
            path=out_file,
            content="plain",
            ctx=ctx,
            src="in.md",
            dur=0.1,
            input_chars=2,
            output_chars=5,
            config=cfg,
        )
        assert not out_file.with_suffix(".meta.json").exists()

    def test_non_atomic_write(self, tmp_path):
        out_file = tmp_path / "result.md"
        ctx = RunContext()
        cfg = SaverConfig(atomic_write=False)
        Saver().write_output(
            path=out_file,
            content="data",
            ctx=ctx,
            src="in.md",
            dur=0.1,
            input_chars=2,
            output_chars=4,
            config=cfg,
        )
        assert out_file.exists()

    def test_strips_ui_noise(self, tmp_path):
        out_file = tmp_path / "result.md"
        ctx = RunContext()
        Saver().write_output(
            path=out_file,
            content="Qwen3\nReal content here",
            ctx=ctx,
            src="in.md",
            dur=0.1,
            input_chars=2,
            output_chars=20,
        )
        content = out_file.read_text()
        assert "Qwen3" not in content
        assert "Real content here" in content
