"""Capabilities: file uploader (AES403).

Implements IUploadProtocol.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Error, Page

from modules.core.src.utility_core_dom_helper import first_visible_locator
from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src import (
    DEFAULT_UPLOAD_CONFIG,
    EVENT_DOCUMENT_PARSED,
    BackoffDelaySec,
    CardRenderTimeoutMs,
    DropdownTimeoutMs,
    FileChooserTimeoutMs,
    FileSizeBytes,
    FileValidationError,
    IUploadProtocol,
    LifecycleEmitter,
    MaxFileSizeMb,
    MaxRetries,
    OptionTimeoutMs,
    UploadConfig,
)
from modules.shared.src import validate_file as _validate_file_util

log = get_logger("capabilities_file_uploader")


# Block 1: Class Definition & Constructor
class FileUploader(IUploadProtocol):
    """Resilient file upload with validation, retry, and DOM recovery."""

    def __init__(self, config: UploadConfig | None = None) -> None:
        if config is not None:
            self.config = config
        else:
            self.config = DEFAULT_UPLOAD_CONFIG

        self.max_file_size_mb = MaxFileSizeMb(float(self.config.max_file_size_mb))
        self.dropdown_timeout_ms = DropdownTimeoutMs(int(self.config.dropdown_timeout_ms))
        self.option_timeout_ms = OptionTimeoutMs(int(self.config.option_timeout_ms))
        self.file_chooser_timeout_ms = FileChooserTimeoutMs(int(self.config.file_chooser_timeout_ms))
        self.card_render_timeout_ms = CardRenderTimeoutMs(int(self.config.card_render_timeout_ms))
        self.max_retries = MaxRetries(int(self.config.max_retries))
        self.backoff_delay_sec = BackoffDelaySec(float(self.config.backoff_delay_sec))

        self.dropdown_selectors = self.config.dropdown_selectors
        self.upload_option_selectors = self.config.upload_option_selectors
        self.card_selectors = self.config.card_selectors

    # ─── Block 2: Public Contract (IUploadProtocol ONLY) ──
    def upload_attachment(
        self,
        page: Page,
        filepath: Path,
        config: dict[str, Any] | None = None,
        emitter: LifecycleEmitter | None = None,
        web_loaded: bool = True,
    ) -> bool:
        """Upload a file as an attachment via the Qwen Web UI."""
        if not web_loaded:
            raise RuntimeError("Cannot upload attachment: web page loading (EVENT_WEB_LOADED) is incomplete")

        if config:
            self.max_file_size_mb = MaxFileSizeMb(config.get("max_file_size_mb", float(self.max_file_size_mb)))
            self.max_retries = MaxRetries(config.get("max_retries", int(self.max_retries)))

        try:
            size_bytes = FileSizeBytes(_validate_file_util(filepath, float(self.max_file_size_mb)))
        except FileValidationError as e:
            log.error("Pre-flight validation failed: %s", e)
            return False

        attempt = 0
        max_attempts = max(1, self.max_retries + 1)

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
                success = self._try_upload_attempt(page, filepath)
                if success:
                    elapsed = time.monotonic()
                    log.info(
                        "File attached successfully in %.2fs (attempt %d): %s",
                        elapsed,
                        attempt,
                        filepath.name,
                    )
                    if emitter:
                        emitter.emit(EVENT_DOCUMENT_PARSED, {"file": str(filepath), "char_count": size_bytes})
                    return True
            except TimeoutError as e:
                log.warning("Timeout during upload attempt %d/%d: %s", attempt, max_attempts, e)
                self._close_dropdown_if_open(page)
            except Error as e:
                log.warning("Unexpected error during upload attempt %d/%d: %s", attempt, max_attempts, e)
                self._close_dropdown_if_open(page)

            if attempt < max_attempts:
                time.sleep(self.backoff_delay_sec * attempt)

        log.error(
            "All %d upload attempts failed for %s after %.2fs",
            max_attempts,
            filepath.name,
            time.monotonic() - size_bytes,
        )
        return False

    def validate_file(self, filepath: Path, max_size_mb: float = 100.0) -> FileSizeBytes:
        """Public protocol method — pre-flight validation returning size in bytes."""
        if max_size_mb != float(self.max_file_size_mb):
            self.max_file_size_mb = MaxFileSizeMb(max_size_mb)
        return FileSizeBytes(_validate_file_util(filepath, float(self.max_file_size_mb)))

    def _close_dropdown_if_open(self, page: Page) -> None:
        """Send Escape key to close orphaned dropdown menus."""
        try:
            page.keyboard.press("Escape")
        except Exception as e:
            log.debug("Cleanup keypress failed (page may be closed or unnavigated): %s", e)

    def _try_upload_attempt(self, page: Page, filepath: Path) -> bool:
        """Execute a single attempt to attach a file via the Qwen Web UI."""
        log.debug("Opening mode-select dropdown using primary/fallback selectors")
        dropdown_element = first_visible_locator(page, self.dropdown_selectors, timeout_ms=1000)

        if not dropdown_element:
            dropdown_element = page.locator(self.dropdown_selectors[0]).first

        dropdown_element.click(timeout=self.dropdown_timeout_ms)

        log.debug("Locating 'Upload attachment' option")
        option_element = first_visible_locator(page, self.upload_option_selectors, timeout_ms=1000)

        if not option_element:
            option_element = page.locator(self.upload_option_selectors[0], has_text="Upload attachment").first
            if not option_element.is_visible(timeout=self.option_timeout_ms):
                option_element = page.locator("text='Upload attachment'").first

        log.debug("Triggering file chooser")
        with page.expect_file_chooser(timeout=self.file_chooser_timeout_ms) as fc:
            option_element.click()

        log.debug("Setting file on file chooser: %s", filepath.name)
        fc.value.set_files(str(filepath))

        log.debug("Waiting for file card attachment indicator to render and complete parsing")
        card_selector_str = ", ".join(self.card_selectors)
        page.locator(card_selector_str).first.wait_for(state="visible", timeout=self.card_render_timeout_ms)
        with contextlib.suppress(Exception):
            page.locator("[class*='loading'], [class*='parsing'], [class*='spin'], .ant-spin").first.wait_for(
                state="hidden", timeout=5000
            )
        time.sleep(2.0)

        return True

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def __repr__(self) -> str:
        """Return string representation of FileUploader."""
        return (
            f"FileUploader(max_size={self.max_file_size_mb}, retries={self.max_retries}, "
            f"backoff={self.backoff_delay_sec})"
        )
