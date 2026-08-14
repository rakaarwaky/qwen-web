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
from modules.shared.src.taxonomy_core_error import FileValidationError
from modules.shared.src.taxonomy_core_event import EVENT_FILE_UPLOADED
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
        self.last_error: Exception | None = None

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

        self.last_error = None
        try:
            size_bytes = FileSizeBytes(_validate_file_util(filepath, float(self.max_file_size_mb)))
        except FileValidationError as e:
            self.last_error = e
            log.error("Pre-flight validation failed: %s", e)
            return False

        attempt = 0
        max_attempts = max(1, self.max_retries + 1)
        started_at = time.monotonic()

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
                    elapsed = time.monotonic() - started_at
                    log.info(
                        "File attached successfully in %.2fs (attempt %d): %s",
                        elapsed,
                        attempt,
                        filepath.name,
                    )
                    if emitter:
                        emitter.emit(
                            EVENT_FILE_UPLOADED,
                            {"file": str(filepath), "byte_count": int(size_bytes), "attempt": attempt},
                        )
                    return True
            except TimeoutError as e:
                self.last_error = e
                log.warning("Timeout during upload attempt %d/%d: %s", attempt, max_attempts, e)
                self._close_dropdown_if_open(page)
            except Error as e:
                self.last_error = e
                log.warning("Unexpected error during upload attempt %d/%d: %s", attempt, max_attempts, e)
                self._close_dropdown_if_open(page)

            if attempt < max_attempts:
                time.sleep(self.backoff_delay_sec * attempt)

        log.error(
            "All %d upload attempts failed for %s after %.2fs",
            max_attempts,
            filepath.name,
            time.monotonic() - started_at,
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
        direct_input = self._find_file_input(page)
        if direct_input is not None:
            log.debug("Setting file through direct Qwen file input selector")
            direct_input.set_input_files(str(filepath))
            try:
                self._wait_for_attachment_card(page, filepath)
                return True
            except (TimeoutError, Error):
                log.debug("Direct file input did not render an attachment card; trying chooser fallback")

        log.debug("Opening mode-select dropdown using primary/fallback selectors")
        dropdown_element = first_visible_locator(page, self.dropdown_selectors, timeout_ms=1000)

        if not dropdown_element:
            dropdown_element = page.locator(self.dropdown_selectors[0]).first

        dropdown_element.click(timeout=self.dropdown_timeout_ms)

        log.debug("Locating upload option using resilient selector fallbacks")
        option_element = first_visible_locator(page, self.upload_option_selectors, timeout_ms=self.option_timeout_ms)

        if not option_element:
            raise TimeoutError(
                "Unable to locate a visible upload action using configured label, aria-label, or data-testid selectors"
            )

        log.debug("Triggering file chooser")
        with page.expect_file_chooser(timeout=self.file_chooser_timeout_ms) as fc:
            option_element.click()

        log.debug("Setting file on file chooser: %s", filepath.name)
        fc.value.set_files(str(filepath))

        self._wait_for_attachment_card(page, filepath)
        return True

    def _find_file_input(self, page: Page) -> Any | None:
        """Find the stable hidden Qwen file input without requiring visibility."""
        for selector in self.config.file_input_selectors:
            locator = page.locator(selector).first
            try:
                if locator.count() > 0:
                    return locator
            except Exception:
                continue
        return None

    def _wait_for_attachment_card(self, page: Page, filepath: Path) -> None:
        """Wait for the uploaded filename to appear in Qwen's live attachment DOM."""
        log.debug("Waiting for Qwen attachment filename node: %s", filepath.name)
        filename_stem = filepath.stem
        filename_selectors = (
            ".fileitem-file-name-text",
            ".fileitem-file-name",
            "[class*='fileitem-file-name-text']",
            "[class*='fileitem-file-name']",
        )
        for selector in filename_selectors:
            matching = page.locator(selector).filter(has_text=filename_stem).last
            try:
                matching.wait_for(state="visible", timeout=self.card_render_timeout_ms)
                break
            except (TimeoutError, Error):
                continue
        else:
            card_selector_str = ", ".join(self.card_selectors)
            page.locator(card_selector_str).last.wait_for(state="visible", timeout=self.card_render_timeout_ms)

        with contextlib.suppress(Exception):
            page.locator("[class*='loading'], [class*='parsing'], [class*='spin'], .ant-spin").last.wait_for(
                state="hidden", timeout=5000
            )
        time.sleep(2.0)

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def __repr__(self) -> str:
        """Return string representation of FileUploader."""
        return (
            f"FileUploader(max_size={self.max_file_size_mb}, retries={self.max_retries}, "
            f"backoff={self.backoff_delay_sec})"
        )
