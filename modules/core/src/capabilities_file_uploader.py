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
from modules.shared.src.contract_core_protocol import IUploadProtocol
from modules.shared.src.taxonomy_config_vo import DEFAULT_UPLOAD_CONFIG, UploadConfig
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_error import (
    FileValidationError,
    UploadVerificationError,
)
from modules.shared.src.taxonomy_core_event import (
    EVENT_DOCUMENT_PARSED,
    EVENT_FILE_UPLOADED,
)
from modules.shared.src.taxonomy_core_vo import (
    BackoffDelaySec,
    CardRenderTimeoutMs,
    DropdownTimeoutMs,
    FileChooserTimeoutMs,
    FileSizeBytes,
    MaxFileSizeMb,
    MaxRetries,
    OptionTimeoutMs,
)
from modules.shared.src.utility_core_validation import validate_file as _validate_file_util

log = get_logger("capabilities_file_uploader")

# Resilient upload option selectors - multiple strategies for finding the upload option
UPLOAD_OPTION_SELECTORS = [
    "text='Upload attachment'",
    "text='Upload File'",
    "[class*='upload']",
    "[aria-label*='upload' i]",
    "[data-testid*='upload']",
    ".ant-dropdown-menu-item:has-text('Upload')",
    "//*[contains(text(), 'Upload') and contains(text(), 'attachment')]",
    "//*[contains(text(), 'Upload') and contains(text(), 'file')]",
]

# Card attachment indicators to verify successful upload
ATTACHMENT_CARD_SELECTORS = [
    "[class*='attachment']",
    "[class*='file-card']",
    "[class*='uploaded']",
    "[data-testid*='attachment']",
    ".ant-upload-list-item",
    "[class*='message-attachment']",
]


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
        """Upload a file as an attachment via the Qwen Web UI.

        Returns True only if the upload is verified. On failure, raises
        UploadVerificationError with details about what went wrong.
        """
        if not web_loaded:
            raise RuntimeError("Cannot upload attachment: web page loading (EVENT_WEB_LOADED) is incomplete")

        if config:
            self.max_file_size_mb = MaxFileSizeMb(config.get("max_file_size_mb", float(self.max_file_size_mb)))
            self.max_retries = MaxRetries(config.get("max_retries", int(self.max_retries)))

        try:
            size_bytes = FileSizeBytes(_validate_file_util(filepath, float(self.max_file_size_mb)))
        except FileValidationError as e:
            log.error("Pre-flight validation failed: %s", e)
            raise UploadVerificationError(f"Pre-flight validation failed: {e}") from e

        attempt = 0
        max_attempts = max(1, self.max_retries + 1)
        start_time = time.monotonic()
        last_error: Exception | None = None

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
                    elapsed = time.monotonic() - start_time
                    log.info(
                        "File attached successfully in %.2fs (attempt %d): %s",
                        elapsed,
                        attempt,
                        filepath.name,
                    )
                    # Emit EVENT_FILE_UPLOADED after verified success
                    if emitter:
                        evt = emitter.emit(
                            EVENT_FILE_UPLOADED,
                            {"file": str(filepath), "char_count": size_bytes, "attempt": attempt},
                        )
                        if evt is None:
                            log.warning("EVENT_FILE_UPLOADED was blocked by lifecycle gate")
                            return False
                    return True
            except TimeoutError as e:
                log.warning("Timeout during upload attempt %d/%d: %s", attempt, max_attempts, e)
                last_error = e
                self._close_dropdown_if_open(page)
            except Error as e:
                log.warning("Unexpected error during upload attempt %d/%d: %s", attempt, max_attempts, e)
                last_error = e
                self._close_dropdown_if_open(page)

            if attempt < max_attempts:
                time.sleep(self.backoff_delay_sec * attempt)

        elapsed = time.monotonic() - start_time
        log.error(
            "All %d upload attempts failed for %s after %.2fs",
            max_attempts,
            filepath.name,
            elapsed,
        )
        error_msg = f"All {max_attempts} upload attempts failed for {filepath.name} after {elapsed:.2f}s"
        if last_error:
            error_msg += f": {last_error}"
        raise UploadVerificationError(error_msg)

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
        """Execute a single attempt to attach a file via the Qwen Web UI.

        Uses resilient selector strategies to locate the upload option and
        verifies successful upload by checking for attachment indicators.
        """
        log.debug("Opening mode-select dropdown using primary/fallback selectors")
        dropdown_element = first_visible_locator(page, self.dropdown_selectors, timeout_ms=1000)

        if not dropdown_element:
            dropdown_element = page.locator(self.dropdown_selectors[0]).first

        dropdown_element.click(timeout=self.dropdown_timeout_ms)

        # Use resilient upload option selectors
        log.debug("Locating upload option using resilient selectors")
        option_element = self._find_upload_option(page)
        if not option_element:
            raise TimeoutError("Could not locate upload option using any known selector")

        log.debug("Triggering file chooser")
        with page.expect_file_chooser(timeout=self.file_chooser_timeout_ms) as fc:
            option_element.click()

        log.debug("Setting file on file chooser: %s", filepath.name)
        fc.value.set_files(str(filepath))

        # Wait for and verify attachment indicator
        if not self._wait_for_attachment(page):
            raise UploadVerificationError(
                f"Upload verification failed: no attachment indicator found after setting file {filepath.name}"
            )

        log.debug("Waiting for file card attachment indicator to render and complete parsing")
        card_selector_str = ", ".join(self.card_selectors)
        page.locator(card_selector_str).first.wait_for(state="visible", timeout=self.card_render_timeout_ms)
        with contextlib.suppress(Exception):
            page.locator("[class*='loading'], [class*='parsing'], [class*='spin'], .ant-spin").first.wait_for(
                state="hidden", timeout=5000
            )
        time.sleep(2.0)

        return True

    def _find_upload_option(self, page: Page) -> Any:
        """Find the upload option using resilient selector strategies.

        Tries multiple selectors in order of reliability to find the
        upload attachment option in the dropdown menu.
        """
        # First try the configured selectors
        option_element = first_visible_locator(page, self.upload_option_selectors, timeout_ms=2000)
        if option_element:
            return option_element

        # Try resilient fallback selectors
        for selector in UPLOAD_OPTION_SELECTORS:
            try:
                loc = page.locator(selector).first
                if loc.is_visible(timeout=self.option_timeout_ms):
                    log.debug("Found upload option with selector: %s", selector)
                    return loc
            except Error:
                continue

        # Final attempt: generic text search for any Upload option
        try:
            upload_options = page.locator("text=Upload").all()
            for opt in upload_options:
                try:
                    if opt.is_visible(timeout=1000):
                        return opt
                except Error:
                    continue
        except Error:
            pass

        return None

    def _wait_for_attachment(self, page: Page) -> bool:
        """Wait for attachment indicator to appear after file selection.

        Returns True if an attachment indicator is found within the timeout.
        """
        for selector in ATTACHMENT_CARD_SELECTORS:
            try:
                loc = page.locator(selector).first
                if loc.count() > 0 and loc.first.is_visible(timeout=self.card_render_timeout_ms):
                    log.debug("Found attachment indicator with selector: %s", selector)
                    return True
            except Error:
                continue
        return False

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def __repr__(self) -> str:
        """Return string representation of FileUploader."""
        return (
            f"FileUploader(max_size={self.max_file_size_mb}, retries={self.max_retries}, "
            f"backoff={self.backoff_delay_sec})"
        )
