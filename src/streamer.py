"""Response streaming detection and stability polling."""
from __future__ import annotations

import time
from typing import Optional

from playwright.sync_api import Page

from .types import (
    LifecycleEmitter,
    EVENT_THINKING_STARTED,
    EVENT_STREAMING_GENERATION,
    EVENT_GENERATION_FINISHED,
)
from .sender import count_messages, latest_message_text
from .observability import get_logger

log = get_logger("streamer")


def wait_for_response(page: Page, timeout_sec: int, msg_count_before: int, emitter: LifecycleEmitter) -> Optional[str]:
    """Wait for new assistant message with stability check."""
    log.info("Waiting for AI response...")
    emitter.emit(EVENT_THINKING_STARTED)
    start = time.time()
    last_text = ""
    stable_count = 0

    while time.time() - start < timeout_sec:
        count = count_messages(page)
        if count > msg_count_before:
            text = latest_message_text(page)
            if text and len(text) > 10:
                if text == last_text:
                    stable_count += 1
                    if stable_count >= 3:
                        emitter.emit(EVENT_GENERATION_FINISHED, {"text_length": len(text)})
                        return text
                else:
                    stable_count = 0
                    last_text = text
                    emitter.emit(EVENT_STREAMING_GENERATION, {"text_length": len(text)})
        time.sleep(1.0)

    return last_text or None
