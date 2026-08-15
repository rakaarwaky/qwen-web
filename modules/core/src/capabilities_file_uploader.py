"""Capabilities: file uploader (AES403).

Implements IUploadProtocol.
"""

from __future__ import annotations

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
from modules.shared.src.taxonomy_core_event import EVENT_DOCUMENT_PARSED, EVENT_FILE_UPLOADED
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
                    self._wait_for_parse_ready(page, filepath)
                    page.wait_for_timeout(500)
                    if emitter:
                        emitter.emit(
                            EVENT_FILE_UPLOADED,
                            {"file": str(filepath), "byte_count": int(size_bytes), "attempt": attempt},
                        )
                        emitter.emit(
                            EVENT_DOCUMENT_PARSED,
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
        baseline_matches = self._attachment_match_count(page, filepath)

        # Direct file input (#filesUpload) doesn't trigger React rendering —
        # always use the dropdown+chooser path which properly fires React handlers.
        log.debug("Opening mode-select dropdown using primary/fallback selectors")
        dropdown_element = first_visible_locator(page, self.dropdown_selectors, timeout_ms=1000)

        if not dropdown_element:
            dropdown_element = page.locator(self.dropdown_selectors[0]).first

        dropdown_element.click(timeout=self.dropdown_timeout_ms)

        # Wait for React to render the dropdown menu before searching for upload option
        page.wait_for_timeout(500)

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

        self._wait_for_attachment_card(page, filepath, baseline_matches)
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

    def _wait_for_attachment_card(self, page: Page, filepath: Path, baseline_matches: int = 0) -> None:
        """Wait for a newly rendered exact filename node in Qwen's live attachment DOM."""
        log.debug("Waiting for exact Qwen attachment filename node: %s", filepath.name)
        deadline = time.monotonic() + (self.card_render_timeout_ms / 1000)
        while time.monotonic() < deadline:
            matches = self._attachment_match_count(page, filepath)
            if matches > baseline_matches or (baseline_matches == 0 and matches > 0):
                self._wait_for_parse_ready(page, filepath)
                return
            page.wait_for_timeout(100)
        raise TimeoutError(f"Exact uploaded filename was not rendered in Qwen attachment DOM: {filepath.name}")

    def _wait_for_parse_ready(self, page: Page, filepath: Path) -> None:
        """Wait until Qwen's matching attachment card exposes a ready state."""
        deadline = time.monotonic() + (self.card_render_timeout_ms / 1000)
        while time.monotonic() < deadline:
            card_selector = ", ".join(self.config.card_selectors)
            card = page.locator(card_selector).filter(has_text=filepath.stem).last
            try:
                if card.count() == 0:
                    page.wait_for_timeout(100)
                    continue
                card_text = card.inner_text().casefold()
                pending_visible = any(
                    card.locator(selector).count() > 0 and card.locator(selector).first.is_visible(timeout=100)
                    for selector in self.config.parse_pending_selectors
                )

                if not pending_visible and "parsing" not in card_text:
                    log.debug("Qwen document parsing is ready for %s", filepath.name)
                    return
            except (TimeoutError, Error):
                pass
            page.wait_for_timeout(200)
        raise TimeoutError(f"Qwen document parsing did not reach ready state: {filepath.name}")

    def _attachment_match_count(self, page: Page, filepath: Path) -> int:
        """Count exact filename matches, preferring full filename nodes over stem-only nodes."""
        normalized_name = " ".join(filepath.name.split()).casefold()
        normalized_stem = " ".join(filepath.stem.split()).casefold()
        for selector, expected in (
            (".fileitem-file-name", normalized_name),
            ("[class*='fileitem-file-name']", normalized_name),
            (".fileitem-file-name-text", normalized_stem),
            ("[class*='fileitem-file-name-text']", normalized_stem),
            # Fallback: any element containing the filename text
            ("", normalized_name),
        ):
            try:
                # Broadest fallback: find any visible text node containing the filename
                locator = page.locator(selector) if selector else page.locator("body")
                visible_texts = []
                for index in range(locator.count()):
                    item = locator.nth(index)
                    try:
                        if item.is_visible():
                            visible_texts.append(item.inner_text())
                    except (TimeoutError, Error):
                        continue
            except (TimeoutError, Error):
                continue
            matches = sum("".join(text.split()).casefold() == expected for text in visible_texts)
            if matches:
                return matches
            # Fallback: check if ANY text on the page contains the filename
            try:
                body_text = page.locator("body").first.inner_text()
                stripped_body = "".join(body_text.split()).casefold()
                stripped_name = "".join(normalized_name.split())
                if stripped_name in stripped_body:
                    return 1
            except (TimeoutError, Error):
                pass
        return 0

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def __repr__(self) -> str:
        """Return string representation of FileUploader."""
        return (
            f"FileUploader(max_size={self.max_file_size_mb}, retries={self.max_retries}, "
            f"backoff={self.backoff_delay_sec})"
        )
