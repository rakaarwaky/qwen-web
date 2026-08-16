"""Tests for the application entry points — `root_cli_main_entry` and `root_mcp_main_entry`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_entry_runs_help() -> None:
    """Running the CLI entry point with --help must print usage and exit 0."""
    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "modules.root_cli_main_entry", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "usage: qwen-web-arwaky" in result.stdout


def test_cli_entry_is_importable() -> None:
    """The CLI entry point must expose a callable `main`."""
    from modules.root_cli_main_entry import main

    assert callable(main)


def test_mcp_entry_is_importable() -> None:
    """The MCP entry point must expose `run_mcp_server` and `main`."""
    from modules.root_mcp_main_entry import main, run_mcp_server

    assert callable(run_mcp_server)
    assert callable(main)
