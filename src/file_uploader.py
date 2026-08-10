"""Enterprise-grade file uploader module for Qwen Web UI automation.

Provides resilient, observable, and configurable file upload capabilities with DOM state
recovery, multi-strategy selector fallbacks, pre-flight file validation, and retry backoff.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .observability import get_logger
from .types import (
    DEFAULT_UPLOAD_CONFIG,
    FileValidationError,
    UploadConfig,
)

log = get_logger("file_uploader")

DEFAULT_CONFIG = DEFAULT_UPLOAD_CONFIG


def validate_file(filepath: Path, max_size_mb: float = 100.0) -> int:
    """Perform pre-flight sanity and security validation on file.

    Args:
        filepath: Path to the target file.
        max_size_mb: Maximum allowed file size in megabytes.

    Returns:
        File size in bytes.

    Raises:
        FileValidationError: If file does not exist, is not a regular file, is unreadable,
                            or exceeds size limits.
    """
    if not filepath.exists():
        raise FileValidationError(f"File does not exist: {filepath}")

    if not filepath.is_file():
        raise FileValidationError(f"Path is not a regular file: {filepath}")

    if not os.access(filepath, os.R_OK):
        raise FileValidationError(f"File is not readable: {filepath}")

    size_bytes = filepath.stat().st_size
    max_bytes = int(max_size_mb * 1024 * 1024)
    if size_bytes > max_bytes:
        raise FileValidationError(
            f"File size ({size_bytes / (1024 * 1024):.2f}MB) exceeds maximum limit "
            f"of {max_size_mb:.2f}MB: {filepath}"
        )

    return size_bytes


def _close_dropdown_if_open(page: Page) -> None:
    """Send Escape key to close orphaned dropdown menus and prevent UI deadlock."""
    try:
        page.keyboard.press("Escape")
    except Exception as e:
        log.debug("Cleanup keypress failed (page may be closed or unnavigated): %s", e)


def _try_upload_attempt(page: Page, filepath: Path, config: UploadConfig) -> bool:
    """Execute a single attempt to attach a file via the Qwen Web UI.

    Raises:
        PlaywrightTimeoutError: On element wait timeouts.
        UIInteractionError: When required elements are missing.
    """
    log.debug("Opening mode-select dropdown using primary/fallback selectors")
    dropdown_element = None
    for selector in config.dropdown_selectors:
        try:
            loc = page.locator(selector).first
            if loc.is_visible(timeout=1000):
                dropdown_element = loc
                break
        except Exception:
            continue

    if not dropdown_element:
        # Final attempt with full standard timeout on primary selector
        dropdown_element = page.locator(config.dropdown_selectors[0]).first

    dropdown_element.click(timeout=config.dropdown_timeout_ms)

    log.debug("Locating 'Upload attachment' option")
    option_element = None
    for selector in config.upload_option_selectors:
        try:
            item = page.locator(selector, has_text="Upload attachment").first
            if item.is_visible(timeout=1000):
                option_element = item
                break
        except Exception:
            continue

    if not option_element:
        option_element = page.locator(config.upload_option_selectors[0], has_text="Upload attachment").first
        if not option_element.is_visible(timeout=config.option_timeout_ms):
            option_element = page.locator("text='Upload attachment'").first

    log.debug("Triggering file chooser")
    with page.expect_file_chooser(timeout=config.file_chooser_timeout_ms) as fc:
        option_element.click()

    log.debug("Setting file on file chooser: %s", filepath.name)
    fc.value.set_files(str(filepath))

    log.debug("Waiting for file card attachment indicator to render")
    card_selector_str = ", ".join(config.card_selectors)
    page.locator(card_selector_str).first.wait_for(
        state="visible", timeout=config.card_render_timeout_ms
    )

    return True


def upload_attachment(
    page: Page,
    filepath: Path,
    config: UploadConfig | None = None,
) -> bool:
    """Upload a file as an attachment via Qwen Web UI mode-select dropdown.

    Resilient wrapper with validation, retries, backoff, and DOM state recovery.

    Args:
        page: Playwright Page instance.
        filepath: Path object pointing to the file to upload.
        config: Optional UploadConfig instance.

    Returns:
        True if the file was attached successfully, False otherwise.
    """
    active_config = config or DEFAULT_CONFIG
    start_time = time.monotonic()

    try:
        size_bytes = validate_file(filepath, max_size_mb=active_config.max_file_size_mb)
    except FileValidationError as e:
        log.error("Pre-flight validation failed: %s", e)
        return False

    attempt = 0
    max_attempts = max(1, active_config.max_retries + 1)

    while attempt < max_attempts:
        attempt += 1
        log.info(
            "Attempt %d/%d to upload attachment: %s (%d bytes)",
            attempt,
            max_attempts,
            filepath.name,
            size_bytes,
        )

        try:
            success = _try_upload_attempt(page, filepath, active_config)
            if success:
                elapsed = time.monotonic() - start_time
                log.info(
                    "File attached successfully in %.2fs (attempt %d): %s",
                    elapsed,
                    attempt,
                    filepath.name,
                )
                return True
        except PlaywrightTimeoutError as e:
            log.warning("Timeout during upload attempt %d/%d: %s", attempt, max_attempts, e)
            _close_dropdown_if_open(page)
        except Exception as e:
            log.warning("Unexpected error during upload attempt %d/%d: %s", attempt, max_attempts, e)
            _close_dropdown_if_open(page)

        if attempt < max_attempts:
            time.sleep(active_config.backoff_delay_sec * attempt)

    elapsed = time.monotonic() - start_time
    log.error("All %d upload attempts failed for %s after %.2fs", max_attempts, filepath.name, elapsed)
    return False
