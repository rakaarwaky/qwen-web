"""Agent: shared prompt-flow orchestration helpers (AES405).

Orchestration steps shared by the direct / file / attachment prompt
orchestrators: lifecycle setup, dispatch, and response waiting.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_dom_query import latest_message_text
from modules.shared.src.contract_core_aggregate import IPromptFileAggregate
from modules.shared.src.contract_core_protocol import (
    IInjectionProtocol,
    ISendProtocol,
    IStreamProtocol,
)
from modules.shared.src.taxonomy_core_error import ResponseDetectionTimeoutError
from modules.shared.src.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_GENERATION_FINISHED,
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_OUTPUT_COPIED,
    EVENT_PROMPT_INJECTED,
    EVENT_SEND_CLICKED,
    EVENT_STREAMING_GENERATION,
    EVENT_THINKING_STARTED,
    EVENT_WEB_LOADED,
    QwenEventType,
)
from modules.shared.src.taxonomy_core_vo import (
    AppConfig,
    HeadlessFlag,
    MessageCount,
    PollIntervalSec,
    PromptText,
    SenderConfig,
    TimeoutSec,
)


class SharedFlowOrchestrator(IPromptFileAggregate):
    """Shared prompt-dispatch and response-wait orchestration steps.

    Provides the common ``dispatch_and_wait_for_response`` flow used by the
    direct, file-only, and attachment prompt orchestrators.
    """

    STANDARD_PROMPT_EVENTS: tuple[QwenEventType, ...] = (
        EVENT_WEB_LOADED,
        EVENT_LOGIN_VERIFIED,
        EVENT_MODEL_VERIFIED,
        EVENT_PROMPT_INJECTED,
        EVENT_SEND_CLICKED,
        EVENT_DISPATCH_ACKNOWLEDGED,
        EVENT_THINKING_STARTED,
        EVENT_STREAMING_GENERATION,
        EVENT_GENERATION_FINISHED,
        EVENT_OUTPUT_COPIED,
    )

    @staticmethod
    def dispatch_and_wait_for_response(
        page: Page,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        emitter: object,
        state: object,
        logger: object,
        filepath: Path,
        prompt: str,
        msg_count_before: int,
        timeout_sec: int,
        active_cfg: AppConfig,
        sender_config: SenderConfig | None = None,
        document_parsed: bool = True,
    ) -> str:
        """Inject prompt, click send, and wait for the AI response."""
        try:
            baseline_response = latest_message_text(page)
        except Exception:
            baseline_response = None

        injector.inject_text(page, PromptText(prompt))
        emitter.emit(EVENT_PROMPT_INJECTED, {"file": str(filepath), "char_count": len(prompt)})

        if sender_config is not None:
            sender.click_send(
                page,
                emitter,
                config=sender_config,
                document_parsed=HeadlessFlag(document_parsed),
            )
        else:
            sender.click_send(page, emitter, document_parsed=HeadlessFlag(document_parsed))

        if not state.dispatch_acknowledged:
            raise RuntimeError("Cannot wait for response: prompt dispatch is incomplete")

        stream_timeout_sec = min(timeout_sec, active_cfg.streaming_timeout)
        response = streamer.wait_for_response(
            page,
            TimeoutSec(stream_timeout_sec),
            MessageCount(msg_count_before),
            emitter,
            polling_interval_sec=PollIntervalSec(active_cfg.poll_interval),
            dispatch_acknowledged=HeadlessFlag(state.dispatch_acknowledged),
            baseline_text=baseline_response,
        )

        if response and len(response.strip()) > 0:
            logger.info("Received response (%d chars)", len(response))
            return response.strip()

        raise ResponseDetectionTimeoutError(
            f"Response detection timeout after {stream_timeout_sec}s: no response detected"
        )


__all__ = ["SharedFlowOrchestrator"]
