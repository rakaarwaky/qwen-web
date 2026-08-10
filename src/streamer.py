"""Response streaming detection and stability polling."""
from __future__ import annotations

import time

from playwright.sync_api import Page, Error as PlaywrightError

from .types import (
    LifecycleEmitter,
    EVENT_THINKING_STARTED,
    EVENT_STREAMING_GENERATION,
    EVENT_GENERATION_FINISHED,
)
from .sender import count_messages, latest_message_text
from .observability import get_logger

log = get_logger("streamer")


def wait_for_response(
    page: Page,
    timeout_sec: int,
    msg_count_before: int,
    emitter: LifecycleEmitter,
    polling_interval_sec: float = 1.0,
    stability_checks: int = 3,
    min_text_length: int = 1,
) -> str | None:
    """Wait for new assistant message with stability check."""
    log.info("Waiting for AI response (timeout: %ds)", timeout_sec)
    emitter.emit(EVENT_THINKING_STARTED)

    start = time.time()
    last_text: str | None = None
    stable_count = 0

    while time.time() - start < timeout_sec:
        try:
            count = count_messages(page)
            if count > msg_count_before:
                text = latest_message_text(page)
                if text is not None and len(text) >= min_text_length:
                    if text == last_text:
                        stable_count += 1
                        if stable_count >= stability_checks:
                            log.info("Response stabilized after %d checks", stability_checks)
                            emitter.emit(EVENT_GENERATION_FINISHED, {"text_length": len(text)})
                            return text
                    else:
                        stable_count = 0
                        last_text = text
                        emitter.emit(EVENT_STREAMING_GENERATION, {"text_length": len(text)})
            time.sleep(polling_interval_sec)
        except PlaywrightError as e:
            log.warning("Browser error during polling: %s", e)
            break
        except Exception as e:
            log.error("Unexpected error during polling: %s", e)
            raise

    log.warning("Timeout after %ds — response may be incomplete", timeout_sec)
    return last_text
