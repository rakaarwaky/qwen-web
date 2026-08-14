"""
Utility layer (utility_core_config_factory): build AppConfig and derive paths.
Stateless functions consumed by Agent orchestrator and StatusFileWriter.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_DONE,
    DEFAULT_FAILED,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_PROC,
    DEFAULT_SESSION,
    DEFAULT_TODO,
)
from modules.shared.src.taxonomy_core_vo import AppConfig


def build_app_config(
    mode: str,
    *,
    input_path: Path | None = None,
    output_path: Path | None = None,
    headless: bool = True,
    interval: int = 3,
    done_path: Path | None = None,
    failed_path: Path | None = None,
    proc_path: Path | None = None,
    session_path: Path | None = None,
    log_path: Path | None = None,
    timeout: int = 300,
    prompt_file: Path | None = None,
    chrome_profile: str = "qwen-cli-profile",
    storage_state_file: Path | None = None,
    disable_sandbox: bool = True,
    request_timeout: int = 120,
    poll_interval: float = 1.0,
    streaming_timeout: int = 180,
    rate_limit_per_minute: int = 60,
    circuit_breaker_threshold: int = 5,
    circuit_breaker_window: int = 30,
    retry_failed: bool = False,
) -> AppConfig:
    """Build a complete AppConfig while preserving every runtime override."""
    return AppConfig(
        mode=mode,
        input_path=input_path or DEFAULT_TODO,
        output_path=output_path or DEFAULT_OUTPUT,
        done_path=done_path or DEFAULT_DONE,
        failed_path=failed_path or DEFAULT_FAILED,
        proc_path=proc_path or DEFAULT_PROC,
        session_path=session_path or DEFAULT_SESSION,
        log_path=log_path or DEFAULT_LOG,
        interval=interval,
        timeout=timeout,
        headless=headless,
        prompt_file=prompt_file,
        chrome_profile=chrome_profile,
        storage_state_file=storage_state_file,
        disable_sandbox=disable_sandbox,
        request_timeout=request_timeout,
        poll_interval=poll_interval,
        streaming_timeout=streaming_timeout,
        rate_limit_per_minute=rate_limit_per_minute,
        circuit_breaker_threshold=circuit_breaker_threshold,
        circuit_breaker_window=circuit_breaker_window,
        retry_failed=retry_failed,
    )
