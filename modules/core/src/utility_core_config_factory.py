"""Config factory utilities.

Utility layer (utility_core_config_factory): build AppConfig and derive paths.
Stateless functions consumed by Agent orchestrator and StatusFileWriter.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_DONE,
    DEFAULT_FAILED,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_PROC,
    DEFAULT_SESSION,
)


def build_app_config(
    mode: str,
    input_path: Path | None = None,
    output_path: Path | None = None,
    headless: bool = True,
    interval: int = 3,
    **overrides,
) -> AppConfig:
    """Build an AppConfig with sensible defaults.

    Parameters
    ----------
    mode : str
        Application mode ("single", "watcher", etc.).
    input_path : optional
        Override for the input directory path.
    output_path : optional
        Override for the output directory path.
    headless : bool
        Whether to run the browser in headless mode.
    interval : int
        Polling interval in seconds (watcher mode).
    **overrides
        Additional AppConfig field overrides.

    Returns
    -------
    AppConfig
        Fully constructed application configuration.

    """
    kwargs = {
        "mode": mode,
        "input_path": input_path or DEFAULT_SESSION,
        "output_path": output_path or DEFAULT_OUTPUT,
        "done_path": DEFAULT_DONE,
        "failed_path": DEFAULT_FAILED,
        "proc_path": DEFAULT_PROC,
        "session_path": DEFAULT_SESSION,
        "log_path": DEFAULT_LOG,
        "interval": interval,
        "headless": headless,
    }
    kwargs.update(overrides)
    return AppConfig(**kwargs)


def status_path_for(log_path: Path) -> Path:
    """Derive the status file path from a log directory.

    Parameters
    ----------
    log_path : Path
        Application log directory.

    Returns
    -------
    Path
        Path to the JSON status file.

    """
    return log_path / "status.json"
