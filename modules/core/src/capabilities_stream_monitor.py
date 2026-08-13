"""Capabilities: stream monitor (AES403).

Implements IStreamProtocol.
"""

from __future__ import annotations

import time

from playwright.sync_api import Error, Page

from modules.core.src.utility_core_dom_helper import is_any_visible, is_selector_visible
from modules.core.src.utility_core_dom_query import count_messages
from modules.core.src.utility_core_dom_query import latest_message_text as _dom_latest
from modules.core.src.utility_core_logger_factory import get_logger
from modules.shared.src.contract_core_protocol import IStreamProtocol
from modules.shared.src.taxonomy_config_vo import StreamerConfig
from modules.shared.src.taxonomy_core_constant import (
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

log = get_logger("capabilities_stream_monitor")


# Block 1: Class Definition & Constructor


class StreamMonitor(IStreamProtocol):
    """Response streaming detection and stability polling."""

    def __init__(
        self,
        config: StreamerConfig | None = None,
    ) -> None:
        if config is not None:
            self.polling_interval_sec = PollIntervalSec(config.polling_interval_sec)
            self.stability_checks = StabilityChecks(config.stability_checks)
            self.min_text_length = MinTextLength(config.min_text_length)
        else:
            self.polling_interval_sec = PollIntervalSec(1.0)
            self.stability_checks = StabilityChecks(4)
            self.min_text_length = MinTextLength(1)

    # ─── Block 2: Public Contract (IStreamProtocol ONLY) ──
    def is_generation_complete(self, page: Page) -> bool:
        """Check if Qwen AI is done generating."""
        try:
            if is_any_visible(page, STOP_BUTTON_SELECTORS):
                return False
            if is_any_visible(page, SEND_DISABLED_SELECTORS):
                return False
            return not is_any_visible(page, TYPING_INDICATOR_SELECTORS)
        except Exception:
            return False

    def is_thinking_active(self, page: Page) -> bool:
        """Check if thinking indicator is active."""
        try:
            typing_selector = ".thinking:not([style*='display: none']), [class*='thinking']"
            return is_selector_visible(page, typing_selector)
        except Error:
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

        baseline_text: str | None = _dom_latest(page)

        start = time.time()
        last_text: str | None = None
        stable_count = 0

        while time.time() - start < timeout_sec:
            try:
                count = count_messages(page)
                if count >= msg_count_before:
                    text = _dom_latest(page)
                    if text is not None and should_treat_as_new_response(text, baseline_text, int(active_min_len)):
                        if text == last_text:
                            stable_count += 1
                            is_complete = self.is_generation_complete(page)
                            if is_stability_satisfied(
                                stable_count, int(active_checks), has_thinking, has_streaming, is_complete
                            ):
                                log.info(
                                    "Response stabilized after %d checks (is_complete=%s)", stable_count, is_complete
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

    def __repr__(self) -> str:
        """Return string representation of StreamMonitor."""
        return (
            f"StreamMonitor(poll={self.polling_interval_sec}, checks={self.stability_checks}, "
            f"min_len={self.min_text_length})"
        )
