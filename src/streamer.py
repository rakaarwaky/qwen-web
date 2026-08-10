"""Response streaming detection and stability polling."""
from __future__ import annotations

import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .observability import get_logger
from .sender import count_messages, latest_message_text
from .types import (
    EVENT_GENERATION_FINISHED,
    EVENT_STREAMING_GENERATION,
    EVENT_THINKING_STARTED,
    AuthRequiredError,
    LifecycleEmitter,
    NetworkTimeoutError,
    OutputValidationError,
)

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
    "oops! there are files still uploading",
    "files still uploading",
    "please wait for the upload to complete",
    "please wait until the uploaded",
    "currently parsing file",
    "finished processing before sending",
    "failed to upload",
    "something went wrong",
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


def is_generation_complete(page: Page) -> bool:
    """Check if Qwen AI is done generating by verifying Send button is re-enabled and no typing indicators exist."""
    try:
        # If stop button exists and is visible -> generation in progress
        stop_btn = page.locator("button[aria-label*='Stop' i], button:has-text('Stop'), [class*='stop-btn'], [class*='icon-stop']")
        if stop_btn.count() > 0 and stop_btn.first.is_visible():
            return False

        # If send button is disabled -> generation in progress
        send_btn_disabled = page.locator("button[aria-label*='Send' i][disabled], button[class*='send' i][disabled]")
        if send_btn_disabled.count() > 0 and send_btn_disabled.first.is_visible():
            return False

        # If typing/thinking indicator exists -> generation in progress
        typing_indicator = page.locator(".thinking:not([style*='display: none']), [class*='typing'], [class*='streaming']")
        if typing_indicator.count() > 0 and typing_indicator.first.is_visible():
            return False

        return True
    except Exception:
        return False


def wait_for_response(
    page: Page,
    timeout_sec: int,
    msg_count_before: int,
    emitter: LifecycleEmitter,
    polling_interval_sec: float = 1.0,
    stability_checks: int = 4,
    min_text_length: int = 1,
    dispatch_acknowledged: bool = True,
) -> str | None:
    """Wait for new assistant message with stability check and output validation."""
    if not dispatch_acknowledged:
        raise RuntimeError("Cannot wait for response: prompt dispatch (EVENT_DISPATCH_ACKNOWLEDGED) is incomplete")

    has_thinking = False
    has_streaming = False

    log.info("Waiting for AI response (timeout: %ds)", timeout_sec)
    emitter.emit(EVENT_THINKING_STARTED)
    has_thinking = True

    start = time.time()
    last_text: str | None = None
    stable_count = 0
    _dom_dumped = False

    while time.time() - start < timeout_sec:
        try:
            # DEBUG: one-shot DOM class dump to discover live selectors
            if not _dom_dumped:
                _dom_dumped = True
                try:
                    _js = """() => {
                        var els = Array.from(document.querySelectorAll('div,p,pre,section,article'));
                        var seen = {};
                        var out = [];
                        for (var i = 0; i < els.length; i++) {
                            var el = els[i];
                            var cls = el.className;
                            if (!cls || typeof cls !== 'string') continue;
                            if (seen[cls]) continue;
                            seen[cls] = true;
                            var txt = (el.innerText || '').trim().slice(0, 60);
                            if (txt.length > 5) out.push(cls + ' ||| ' + txt);
                            if (out.length >= 60) break;
                        }
                        return out.join('\\n');
                    }"""
                    dom_dump = page.evaluate(_js)
                    log.info("DOM_DEBUG_DUMP:\n%s", dom_dump)
                except Exception as _de:
                    log.warning("DOM dump failed: %s", _de)

            count = count_messages(page)
            if count >= msg_count_before:
                text = latest_message_text(page)
                if text is not None and len(text) >= min_text_length:
                    if text == last_text:
                        stable_count += 1
                        is_complete = is_generation_complete(page)
                        if has_thinking and has_streaming and stable_count >= stability_checks and is_complete:
                            log.info("Response stabilized after %d checks (complete=%s)", stable_count, is_complete)
                            validate_response_content(text)
                            emitter.emit(EVENT_GENERATION_FINISHED, {"text_length": len(text)})
                            return text
                    else:
                        if has_thinking:
                            has_streaming = True
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
