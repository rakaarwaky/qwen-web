"""Tests for the package entry point — `python -m modules` runs the CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_modules_package_runs_cli() -> None:
    """Running `python -m modules --help` must print usage and exit 0."""
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "modules", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "usage: qwen-cli" in result.stdout
