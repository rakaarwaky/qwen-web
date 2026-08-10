"""File upload via Qwen's mode-select dropdown → file chooser."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from .observability import get_logger

log = get_logger("file_uploader")


def upload_attachment(page: Page, filepath: Path) -> bool:
    """Upload file as attachment via mode-select dropdown. Returns True if attached."""
    try:
        page.locator(".mode-select-open").first.click(timeout=5000)
        page.wait_for_timeout(500)
        item = page.locator(".mode-select-dropdown-item", has_text="Upload attachment").first
        if not item.is_visible(timeout=3000):
            item = page.locator("text='Upload attachment'").first
        with page.expect_file_chooser(timeout=8000) as fc:
            item.click()
        fc.value.set_files(str(filepath))
        page.wait_for_timeout(1800)
        attached = bool(page.evaluate("""() => {
            const s=['.file-card-list','.fileitem-btn','.message-input-column-file',
                     '[class*="file-card"]','[class*="file-item"]','[class*="fileitem"]'];
            for(const sel of s){for(const el of document.querySelectorAll(sel)){
                if(el.offsetWidth>0&&el.offsetHeight>0) return true;}}
            return false;}"""))
        if attached:
            log.info("File attached successfully: %s", filepath.name)
        else:
            log.warning("File upload did not produce visible attachment card")
        return attached
    except Exception as e:
        log.warning("File upload failed: %s", e)
        return False
