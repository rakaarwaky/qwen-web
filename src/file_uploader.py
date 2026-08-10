"""File upload via Qwen's mode-select dropdown → file chooser."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from .observability import get_logger

log = get_logger("file_uploader")


def upload_attachment(page: Page, filepath: Path) -> bool:
    """Upload file as attachment via mode-select dropdown. Returns True if attached."""
    if not filepath.is_file():
        log.error("File not found: %s", filepath)
        return False

    try:
        log.debug("Opening mode-select dropdown")
        page.locator(".mode-select-open").first.click(timeout=5000)

        log.debug("Looking for 'Upload attachment' option")
        item = page.locator(".mode-select-dropdown-item", has_text="Upload attachment").first
        if not item.is_visible(timeout=3000):
            log.debug("Primary selector not visible, falling back to text search")
            item = page.locator("text='Upload attachment'").first

        log.debug("Triggering file chooser")
        with page.expect_file_chooser(timeout=8000) as fc:
            item.click()

        log.debug("Setting file: %s", filepath.name)
        fc.value.set_files(str(filepath))

        log.debug("Waiting for file card to render")
        page.locator(
            ".file-card-list, .fileitem-btn, .message-input-column-file, "
            "[class*='file-card'], [class*='file-item'], [class*='fileitem']"
        ).first.wait_for(state="visible", timeout=5000)

        log.info("File attached successfully: %s", filepath.name)
        return True

    except PlaywrightTimeoutError as e:
        log.error("Timeout during upload (UI slow or unresponsive): %s", e)
        return False
    except Exception as e:
        log.exception("Unexpected error during upload: %s", e)
        return False
