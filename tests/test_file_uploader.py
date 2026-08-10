"""Unit tests for enterprise file_uploader module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.file_uploader import (
    FileValidationError,
    UploadConfig,
    _close_dropdown_if_open,
    upload_attachment,
    validate_file,
)


def test_validate_file_success(tmp_path: Path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    size = validate_file(test_file, max_size_mb=1.0)
    assert size == 11


def test_validate_file_non_existent():
    path = Path("/non/existent/file.txt")
    with pytest.raises(FileValidationError, match="does not exist"):
        validate_file(path)


def test_validate_file_too_large(tmp_path: Path):
    test_file = tmp_path / "big.bin"
    test_file.write_bytes(b"0" * 1024 * 1024 * 2)  # 2 MB

    with pytest.raises(FileValidationError, match="exceeds maximum limit"):
        validate_file(test_file, max_size_mb=1.0)


def test_close_dropdown_if_open():
    mock_page = MagicMock()
    _close_dropdown_if_open(mock_page)
    mock_page.keyboard.press.assert_called_once_with("Escape")


def test_upload_attachment_success(tmp_path: Path):
    test_file = tmp_path / "sample.pdf"
    test_file.write_text("pdf content")

    mock_page = MagicMock()
    mock_locator = MagicMock()
    mock_page.locator.return_value = mock_locator
    mock_locator.first = mock_locator
    mock_locator.is_visible.return_value = True

    mock_file_chooser = MagicMock()
    mock_expect_context = MagicMock()
    mock_expect_context.__enter__.return_value = mock_file_chooser
    mock_page.expect_file_chooser.return_value = mock_expect_context

    result = upload_attachment(mock_page, test_file)

    assert result is True
    mock_file_chooser.value.set_files.assert_called_once_with(str(test_file))


def test_upload_attachment_timeout_with_retry_and_recovery(tmp_path: Path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("content")

    mock_page = MagicMock()
    mock_locator = MagicMock()
    mock_page.locator.return_value = mock_locator
    mock_locator.first = mock_locator
    mock_locator.click.side_effect = PlaywrightTimeoutError("UI timeout")

    config = UploadConfig(max_retries=1, backoff_delay_sec=0.01)
    result = upload_attachment(mock_page, test_file, config=config)

    assert result is False
    # Check escape key attempt on retry cleanup
    assert mock_page.keyboard.press.call_count >= 1
