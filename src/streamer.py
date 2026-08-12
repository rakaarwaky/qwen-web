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
        return not (typing_indicator.count() > 0 and typing_indicator.first.is_visible())
    except Exception:
        return False


def is_thinking_active(page: Page, msg_count_before: int) -> bool:
    """Check if Qwen AI thinking/reasoning indicator is actively visible inside a new assistant response turn."""
    try:
        current_turns = count_messages(page)
        if current_turns <= msg_count_before:
            return False
        # Specific assistant thinking indicators in active chat turn
        thinking_loc = page.locator(
            ".chat-message-assistant .thinking, "
            "[data-role='assistant'] [class*='thinking'], "
            ".chat-message-assistant [class*='thought-process'], "
            ".qwen-markdown .thinking"
        )
        if thinking_loc.count() > 0 and thinking_loc.first.is_visible():
            return True
    except Exception:
        pass
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

    # Capture baseline page text so we can detect genuinely new content
    baseline_text: str | None = latest_message_text(page)

    start = time.time()
    last_text: str | None = None
    stable_count = 0

    while time.time() - start < timeout_sec:
        try:
            # Detect real DOM thinking phase dynamically only after new chat turn appears
            if not has_thinking and is_thinking_active(page, msg_count_before):
                emitter.emit(EVENT_THINKING_STARTED)
                has_thinking = True

            count = count_messages(page)
            if count >= msg_count_before:
                text = latest_message_text(page)
                # Only treat as new response if text differs from baseline page content
                if text is not None and len(text) >= min_text_length and text != baseline_text:
                    if text == last_text:
                        stable_count += 1
                        is_complete = is_generation_complete(page)
                        force_complete = stable_count >= stability_checks * 2
                        if has_streaming and stable_count >= stability_checks and (is_complete or force_complete):
                            log.info("Response stabilized after %d checks (is_complete=%s, forced=%s)", stable_count, is_complete, force_complete)
                            validate_response_content(text)
                            emitter.emit(EVENT_GENERATION_FINISHED, {"text_length": len(text)})
                            return text
                    else:
                        has_streaming = True
                        stable_count = 0
                        last_text = text
                        emitter.emit(EVENT_STREAMING_GENERATION, {"text_length": len(text)})

            # Pure DOM Mutation Event Listener — wake immediately when DOM mutates, without fixed time.sleep
            try:
                page.wait_for_function(
                    """
                    (args) => {
                        const [oldTurnCount, oldText] = args;
                        const turns = document.querySelectorAll('[class*="chat-message"], [class*="message-item"], [class*="virtual-list-item"], [class*="turn"]').length;
                        if (turns > oldTurnCount) return true;
                        const selectors = [
                            '.chat-message-assistant .markdown-body:not(.thinking):not([class*="thought"])',
                            '.chat-message-assistant:not(.thinking)',
                            '[class*="assistant"] .markdown-body:not(.thinking):not([class*="thought"])',
                            '[class*="assistant"] [class*="markdown"]:not(.thinking):not([class*="thought"])',
                            '[data-role="assistant"] .markdown-body:not(.thinking):not([class*="thought"])',
                            '.qwen-markdown:not(.thinking):not([class*="thought"])'
                        ];
                        for (let i = 0; i < selectors.length; i++) {
                            const els = document.querySelectorAll(selectors[i]);
                            if (els.length > 0) {
                                const currentText = (els[els.length - 1].innerText || '').trim();
                                if (currentText && currentText !== oldText) return true;
                            }
                        }
                        const thinking = document.querySelector('.thinking:not([style*="display: none"]), [class*="thought"]:not([style*="display: none"])');
                        return thinking !== null;
                    }
                    """,
                    arg=(count if 'count' in locals() else msg_count_before, last_text or baseline_text or ""),
                    timeout=max(500, int(polling_interval_sec * 1000)),
                )
            except PlaywrightTimeoutError:
                pass
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

    raise TimeoutError(f"Timeout after {timeout_sec}s: no valid AI assistant response detected on chat.qwen.ai")
