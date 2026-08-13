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
    done_path: Path | None = None,
    failed_path: Path | None = None,
    proc_path: Path | None = None,
    session_path: Path | None = None,
    log_path: Path | None = None,
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
    done_path : optional
        Override for the done directory path.
    failed_path : optional
        Override for the failed directory path.
    proc_path : optional
        Override for the processing directory path.
    session_path : optional
        Override for the session directory path.
    log_path : optional
        Override for the log directory path.

    Returns
    -------
    AppConfig
        Fully constructed application configuration.

    """
    return AppConfig(
        mode=mode,
        input_path=input_path or DEFAULT_SESSION,
        output_path=output_path or DEFAULT_OUTPUT,
        done_path=done_path or DEFAULT_DONE,
        failed_path=failed_path or DEFAULT_FAILED,
        proc_path=proc_path or DEFAULT_PROC,
        session_path=session_path or DEFAULT_SESSION,
        log_path=log_path or DEFAULT_LOG,
        interval=interval,
        headless=headless,
    )
