"""Unit tests for 10/10 error handling & resilience coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.saver import write_output
from src.streamer import validate_response_content
from src.types import (
    AuthRequiredError,
    CircuitBreaker,
    OutputValidationError,
    OutputWriteError,
    RateLimiter,
    RunContext,
)


def test_validate_response_content_valid():
    validate_response_content("This is a valid response from Qwen AI.")


def test_validate_response_content_empty():
    with pytest.raises(OutputValidationError, match="Response content is empty"):
        validate_response_content("   ")


def test_validate_response_content_captcha():
    with pytest.raises(AuthRequiredError, match="CAPTCHA"):
        validate_response_content("Please verify you are human to proceed.")


def test_validate_response_content_server_error():
    with pytest.raises(OutputValidationError, match="Server error"):
        validate_response_content("502 Bad Gateway - Nginx")


def test_circuit_breaker_tripping():
    cb = CircuitBreaker(threshold=3, window_sec=30)
    assert not cb.is_tripped

    cb.record_failure()
    cb.record_failure()
    assert not cb.is_tripped

    cb.record_failure()
    assert cb.is_tripped

    cb.record_success()
    assert not cb.is_tripped


def test_rate_limiter_acquisition():
    rl = RateLimiter(max_per_minute=10)
    rl.acquire()
    assert len(rl._timestamps) == 1


def test_saver_error_handling(tmp_path: Path):
    ctx = RunContext()
    # Provide directory as target file to trigger OSError -> OutputWriteError
    dir_as_file = tmp_path / "dir_target"
    dir_as_file.mkdir()

    with pytest.raises(OutputWriteError, match="Failed to write output file"):
        write_output(dir_as_file, "test content", ctx, "src.md", 1.0, 10, 12)
