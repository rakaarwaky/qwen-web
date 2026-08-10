"""Response streaming detection and stability polling."""
from __future__ import annotations

import time

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

from .types import (
    AuthRequiredError,
    LifecycleEmitter,
    NetworkTimeoutError,
    OutputValidationError,
    EVENT_THINKING_STARTED,
    EVENT_STREAMING_GENERATION,
    EVENT_GENERATION_FINISHED,
)
from .sender import count_messages, latest_message_text
from .observability import get_logger

log = get_logger("streamer")

CHALLENGE_KEYWORDS: tuple[str, ...] = (
    "just a moment",
    "attention required!",
    "verify you are human",
    "enable javascript and cookies",
    "502 bad gateway",
    "504 gateway time-out",
    "service unavailable",
    "access denied",
)


def validate_response_content(text: str) -> None:
    """Validate AI response text for server error pages or CAPTCHA challenges."""
    if not text or not text.strip():
        raise OutputValidationError("Response content is empty")

    text_lower = text.lower()
    for kw in CHALLENGE_KEYWORDS:
        if kw in text_lower and len(text) < 500:
            if "verify you are human" in text_lower or "attention required!" in text_lower:
                raise AuthRequiredError(f"CAPTCHA / Bot detection challenge detected: '{kw}'")
            raise OutputValidationError(f"Server error or challenge page detected in output: '{kw}'")


def wait_for_response(
    page: Page,
    timeout_sec: int,
    msg_count_before: int,
    emitter: LifecycleEmitter,
    polling_interval_sec: float = 1.0,
    stability_checks: int = 3,
    min_text_length: int = 1,
) -> str:
    """Wait for new assistant message with stability check and output validation."""
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
                            validate_response_content(text)
                            emitter.emit(EVENT_GENERATION_FINISHED, {"text_length": len(text)})
                            return text
                    else:
                        stable_count = 0
                        last_text = text
                        emitter.emit(EVENT_STREAMING_GENERATION, {"text_length": len(text)})
            time.sleep(polling_interval_sec)
        except PlaywrightTimeoutError as e:
            raise NetworkTimeoutError(f"Browser network timeout during streaming poll: {e}") from e
        except PlaywrightError as e:
            log.warning("Browser error during polling: %s", e)
            raise NetworkTimeoutError(f"Browser IPC error during streaming poll: {e}") from e
        except (AuthRequiredError, OutputValidationError):
            raise
        except Exception as e:
            log.error("Unexpected error during polling: %s", e)
            raise

    if last_text is not None:
        validate_response_content(last_text)
        return last_text

    log.warning("Timeout after %ds — no response detected", timeout_sec)
    return None
