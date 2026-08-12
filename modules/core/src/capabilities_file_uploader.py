"""Capabilities: file uploader (AES403).

Implements IUploadProtocol.
"""

from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from modules.shared.src.contract_core_protocol import IUploadProtocol
from modules.shared.src.taxonomy_core_event import LifecycleEmitter
from modules.shared.src.taxonomy_core_vo import (
    EVENT_DOCUMENT_PARSED,
    BackoffDelaySec,
    CardRenderTimeoutMs,
    DropdownTimeoutMs,
    FileChooserTimeoutMs,
    MaxFileSizeMb,
    MaxRetries,
    OptionTimeoutMs,
)
from modules.shared.src.taxonomy_domain_error import (
    FileValidationError,
)

log = __import__("logging").getLogger("capabilities_file_uploader")

DEFAULT_MAX_FILE_SIZE_MB = MaxFileSizeMb(100.0)
DEFAULT_DROPDOWN_TIMEOUT_MS = DropdownTimeoutMs(5000)
DEFAULT_OPTION_TIMEOUT_MS = OptionTimeoutMs(3000)
DEFAULT_FILE_CHOOSER_TIMEOUT_MS = FileChooserTimeoutMs(8000)
DEFAULT_CARD_RENDER_TIMEOUT_MS = CardRenderTimeoutMs(5000)
DEFAULT_MAX_RETRIES = MaxRetries(2)
DEFAULT_BACKOFF_DELAY_SEC = BackoffDelaySec(1.0)


class FileUploader(IUploadProtocol):
    """Resilient file upload with validation, retry, and DOM recovery."""

    def __init__(
        self,
        max_file_size_mb: MaxFileSizeMb = DEFAULT_MAX_FILE_SIZE_MB,
        dropdown_timeout_ms: DropdownTimeoutMs = DEFAULT_DROPDOWN_TIMEOUT_MS,
        option_timeout_ms: OptionTimeoutMs = DEFAULT_OPTION_TIMEOUT_MS,
        file_chooser_timeout_ms: FileChooserTimeoutMs = DEFAULT_FILE_CHOOSER_TIMEOUT_MS,
        card_render_timeout_ms: CardRenderTimeoutMs = DEFAULT_CARD_RENDER_TIMEOUT_MS,
        max_retries: MaxRetries = DEFAULT_MAX_RETRIES,
        backoff_delay_sec: BackoffDelaySec = DEFAULT_BACKOFF_DELAY_SEC,
    ) -> None:
        self.max_file_size_mb = max_file_size_mb
        self.dropdown_timeout_ms = dropdown_timeout_ms
        self.option_timeout_ms = option_timeout_ms
        self.file_chooser_timeout_ms = file_chooser_timeout_ms
        self.card_render_timeout_ms = card_render_timeout_ms
        self.max_retries = max_retries
        self.backoff_delay_sec = backoff_delay_sec

        self.dropdown_selectors = (
            ".mode-select-open",
            "[class*='mode-select']",
            "button:has-text('Upload')",
        )
        self.upload_option_selectors = (
            ".mode-select-dropdown-item",
            "text='Upload attachment'",
            "text='Upload file'",
        )
        self.card_selectors = (
            ".file-card-list",
            ".fileitem-btn",
            ".message-input-column-file",
            "[class*='file-card']",
            "[class*='file-item']",
            "[class*='fileitem']",
        )

    def upload_attachment(
        self,
        page: Page,
        filepath: Path,
        _config: Any | None = None,
        emitter: LifecycleEmitter | None = None,
        web_loaded: bool = True,
    ) -> bool:
        """Upload a file as an attachment via the Qwen Web UI."""
        if not web_loaded:
            raise RuntimeError("Cannot upload attachment: web page loading (EVENT_WEB_LOADED) is incomplete")

        try:
            size_bytes = self._validate_file(filepath)
        except FileValidationError as e:
            log.error("Pre-flight validation failed: %s", e)
            return False

        attempt = 0
        max_attempts = max(1, self.max_retries + 1)

        while attempt < max_attempts:
            attempt += 1
            log.info(
                "Attempt %d/%d to upload attachment: %s (%d bytes)",
                attempt, max_attempts, filepath.name, size_bytes,
            )

            try:
                success = self._try_upload_attempt(page, filepath)
                if success:
                    elapsed = time.monotonic()
                    log.info(
                        "File attached successfully in %.2fs (attempt %d): %s",
                        elapsed, attempt, filepath.name,
                    )
                    if emitter:
                        emitter.emit(EVENT_DOCUMENT_PARSED, {"file": str(filepath), "char_count": size_bytes})
                    return True
            except PlaywrightTimeoutError as e:
                log.warning("Timeout during upload attempt %d/%d: %s", attempt, max_attempts, e)
                self._close_dropdown_if_open(page)
            except Exception as e:
                log.warning("Unexpected error during upload attempt %d/%d: %s", attempt, max_attempts, e)
                self._close_dropdown_if_open(page)

            if attempt < max_attempts:
                time.sleep(self.backoff_delay_sec * attempt)

        log.error(
            "All %d upload attempts failed for %s after %.2fs",
            max_attempts, filepath.name, time.monotonic() - size_bytes
        )
        return False

    def _validate_file(self, filepath: Path) -> int:
        """Perform pre-flight sanity and security validation."""
        if not filepath.exists():
            raise FileValidationError(f"File does not exist: {filepath}")

        if not filepath.is_file():
            raise FileValidationError(f"Path is not a regular file: {filepath}")

        if not os.access(filepath, os.R_OK):
            raise FileValidationError(f"File is not readable: {filepath}")

        size_bytes = filepath.stat().st_size
        max_bytes = int(self.max_file_size_mb * 1024 * 1024)
        if size_bytes > max_bytes:
            raise FileValidationError(
                f"File size ({size_bytes / (1024 * 1024):.2f}MB) exceeds maximum limit "
                f"of {self.max_file_size_mb:.2f}MB: {filepath}"
            )

        return size_bytes

    def validate_file(self, filepath: Path, max_size_mb: float = 100.0) -> int:
        """Public protocol method — pre-flight validation returning size in bytes."""
        if max_size_mb != float(self.max_file_size_mb):
            self.max_file_size_mb = MaxFileSizeMb(max_size_mb)
        return self._validate_file(filepath)

    def _close_dropdown_if_open(self, page: Page) -> None:
        """Send Escape key to close orphaned dropdown menus."""
        try:
            page.keyboard.press("Escape")
        except Exception as e:
            log.debug("Cleanup keypress failed (page may be closed or unnavigated): %s", e)

    def _try_upload_attempt(self, page: Page, filepath: Path) -> bool:
        """Execute a single attempt to attach a file via the Qwen Web UI."""
        log.debug("Opening mode-select dropdown using primary/fallback selectors")
        dropdown_element = None
        for selector in self.dropdown_selectors:
            try:
                loc = page.locator(selector).first
                if loc.is_visible(timeout=1000):
                    dropdown_element = loc
                    break
            except Exception:
                continue

        if not dropdown_element:
            dropdown_element = page.locator(self.dropdown_selectors[0]).first

        dropdown_element.click(timeout=self.dropdown_timeout_ms)

        log.debug("Locating 'Upload attachment' option")
        option_element = None
        for selector in self.upload_option_selectors:
            try:
                item = page.locator(selector).first
                if item.is_visible(timeout=1000):
                    option_element = item
                    break
            except Exception:
                continue

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
        page.locator(card_selector_str).first.wait_for(
            state="visible", timeout=self.card_render_timeout_ms
        )
        with contextlib.suppress(Exception):
            page.locator("[class*='loading'], [class*='parsing'], [class*='spin'], .ant-spin").first.wait_for(
                state="hidden", timeout=5000
            )
        time.sleep(2.0)

        return True


# Module-level convenience function
def upload_attachment(
    page: Page,
    filepath: Path,
    _config: dict[str, Any] | None = None,
    emitter: LifecycleEmitter | None = None,
    web_loaded: bool = True,
) -> bool:
    """Upload attachment (module-level convenience)."""
    uploader = FileUploader()
    return uploader.upload_attachment(page, filepath, _config, emitter, web_loaded)
