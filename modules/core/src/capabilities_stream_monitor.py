"""Capabilities: stream monitor (AES403).

Implements IStreamProtocol.
"""

import time
from typing import Any

from playwright.sync_api import Error, Page, TimeoutError

from modules.shared.src.contract_core_protocol import IStreamProtocol
from modules.shared.src.taxonomy_core_constant import (
    COMBINED_MESSAGE_SELECTOR,
    JS_COUNT_TURNS,
    JS_GET_RESPONSE_TEXT,
    SEND_DISABLED_SELECTORS,
    STOP_BUTTON_SELECTORS,
    TYPING_INDICATOR_SELECTORS,
)
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter
from modules.shared.src.taxonomy_core_vo import (
    EVENT_GENERATION_FINISHED,
    EVENT_STREAMING_GENERATION,
    EVENT_THINKING_STARTED,
    MinTextLength,
    PollIntervalSec,
    ResponseText,
    StabilityChecks,
)
from modules.shared.src.taxonomy_domain_error import AuthRequiredError, NetworkTimeoutError, OutputValidationError
from modules.shared.src.utility_core_events import is_stability_satisfied, should_treat_as_new_response
from modules.shared.src.utility_core_validation import validate_response_content

log = __import__("logging").getLogger("capabilities_stream_monitor")

DEFAULT_POLLING_INTERVAL_SEC = PollIntervalSec(1.0)
DEFAULT_STABILITY_CHECKS = StabilityChecks(4)
DEFAULT_MIN_TEXT_LENGTH = MinTextLength(1)



# Block 1: Class Definition & Constructor


class StreamMonitor(IStreamProtocol):
    """Response streaming detection and stability polling."""

    def __init__(
        self,
        polling_interval_sec: PollIntervalSec = DEFAULT_POLLING_INTERVAL_SEC,
        stability_checks: StabilityChecks = DEFAULT_STABILITY_CHECKS,
        min_text_length: MinTextLength = DEFAULT_MIN_TEXT_LENGTH,
    ) -> None:
        self.polling_interval_sec = polling_interval_sec
        self.stability_checks = stability_checks
        self.min_text_length = min_text_length

# Block 2: Public Contract


    def is_generation_complete(self, page: Page) -> bool:
        """Check if Qwen AI is done generating."""
        try:
            stop_btn = page.locator(STOP_BUTTON_SELECTORS)
            if stop_btn.count() > 0 and stop_btn.first.is_visible():
                return False

            send_btn_disabled = page.locator(SEND_DISABLED_SELECTORS)
            if send_btn_disabled.count() > 0 and send_btn_disabled.first.is_visible():
                return False

            typing_indicator = page.locator(TYPING_INDICATOR_SELECTORS)
            return not (typing_indicator.count() > 0 and typing_indicator.first.is_visible())
        except Exception:
            return False

    def is_thinking_active(self, page: Page) -> bool:
        """Check if thinking indicator is active."""
        try:
            typing_indicator = page.locator(".thinking:not([style*='display: none']), [class*='thinking']")
            return typing_indicator.count() > 0 and typing_indicator.first.is_visible()
        except Exception:
            return False

    def wait_for_response(
        self,
        page: Page,
        timeout_sec: int,
        msg_count_before: int,
        emitter: LifecycleEmitter,
        polling_interval_sec: float = 1.0,
        stability_checks: int = 4,
        min_text_length: int = 1,
        dispatch_acknowledged: bool = True,
    ) -> ResponseText | None:
        """Wait for new assistant message with stability check and output validation."""
        if not dispatch_acknowledged:
            raise RuntimeError("Cannot wait for response: prompt dispatch (EVENT_DISPATCH_ACKNOWLEDGED) is incomplete")

        active_poll = PollIntervalSec(polling_interval_sec)
        active_checks = StabilityChecks(stability_checks)
        active_min_len = MinTextLength(min_text_length)

        has_thinking = False
        has_streaming = False

        log.info("Waiting for AI response (timeout: %ds)", timeout_sec)
        emitter.emit(EVENT_THINKING_STARTED)
        has_thinking = True

        baseline_text: str | None = _latest_message_text(page)

        start = time.time()
        last_text: str | None = None
        stable_count = 0

        while time.time() - start < timeout_sec:
            try:
                count = _count_messages(page)
                if count >= msg_count_before:
                    text = _latest_message_text(page)
                    if text is not None and should_treat_as_new_response(text, baseline_text, int(active_min_len)):
                        if text == last_text:
                            stable_count += 1
                            is_complete = self.is_generation_complete(page)
                            if is_stability_satisfied(
                                stable_count, int(active_checks), has_thinking, has_streaming, is_complete
                            ):
                                log.info(
                                    "Response stabilized after %d checks (is_complete=%s)",
                                    stable_count, is_complete
                                )
                                validate_response_content(text)
                                emitter.emit(EVENT_GENERATION_FINISHED, {"text_length": len(text)})
                                return ResponseText(text)
                        else:
                            if has_thinking:
                                has_streaming = True
                                stable_count = 0
                                last_text = text
                                emitter.emit(EVENT_STREAMING_GENERATION, {"text_length": len(text)})
                time.sleep(active_poll)
            except TimeoutError as e:
                raise NetworkTimeoutError(f"Browser network timeout during streaming poll: {e}") from e
            except Error as e:
                log.warning("Browser error during polling: %s", e)
                raise NetworkTimeoutError(f"Browser IPC error during streaming poll: {e}") from e
            except (AuthRequiredError, OutputValidationError):
                raise
            except Exception as e:
                log.error("Unexpected error during polling: %s", e)
                raise

        if last_text is not None:
            validate_response_content(last_text)
            return ResponseText(last_text)

        log.warning("Timeout after %ds — no response detected", timeout_sec)
        return None

# Block 3: Dunder Methods, Factories & Helpers


    def __repr__(self) -> str:
        """Return string representation of StreamMonitor."""
        return (
            f"StreamMonitor(poll={self.polling_interval_sec}, checks={self.stability_checks}, "
            f"min_len={self.min_text_length})"
        )


# Module-level convenience functions
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
    """Wait for response (module-level convenience)."""
    monitor = StreamMonitor(
        polling_interval_sec=PollIntervalSec(polling_interval_sec),
        stability_checks=StabilityChecks(stability_checks),
        min_text_length=MinTextLength(min_text_length),
    )
    return monitor.wait_for_response(
        page,
        timeout_sec,
        msg_count_before,
        emitter,
        polling_interval_sec,
        stability_checks,
        min_text_length,
        dispatch_acknowledged,
    )


def is_generation_complete(page: Page) -> bool:
    """Check if generation complete (module-level convenience)."""
    monitor = StreamMonitor()
    return monitor.is_generation_complete(page)


def is_thinking_active(page: Page) -> bool:
    """Check if thinking active (module-level convenience)."""
    monitor = StreamMonitor()
    return monitor.is_thinking_active(page)


def _safe_count(cnt: Any) -> int:
    """Return 0 when count() returns a non-int (e.g. MagicMock) for test safety."""
    return cnt if isinstance(cnt, int) else 0


def _count_messages(page: Page) -> int:
    """Count chat turns using JS evaluate — robust against CSS modules and virtual DOM."""
    try:
        count = page.evaluate(JS_COUNT_TURNS)
        if isinstance(count, int) and count > 0:
            return count
    except Error:
        pass
    try:
        return page.locator(COMBINED_MESSAGE_SELECTOR).count()
    except Error:
        return 0


def _latest_message_text(page: Page) -> str | None:
    """Get the longest text block on the page excluding input/UI chrome — JS-based."""
    try:
        text = page.evaluate(JS_GET_RESPONSE_TEXT)
        if text and len(text.strip()) > 0:
            return str(text.strip())
    except Error:
        pass
    try:
        locator = page.locator(COMBINED_MESSAGE_SELECTOR)
        cnt = locator.count()
        if isinstance(cnt, int) and cnt > 0:
            text = locator.last.text_content()
            if text is not None:
                return str(text.strip())
    except Error:
        pass
    return None

