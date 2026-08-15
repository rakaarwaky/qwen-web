"""Agent: direct text prompt orchestrator (AES405).

Orchestrates direct string text prompt execution without prompt file on disk.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_config_factory import build_app_config
from modules.core.src.utility_core_dom_query import latest_message_text
from modules.core.src.utility_core_error_mapping import to_error_response
from modules.shared.src.contract_core_aggregate import IDirectPromptAggregate
from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
    IInjectionProtocol,
    IObservabilityProtocol,
    ISendProtocol,
    IStreamProtocol,
)
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_OUTPUT,
)
from modules.shared.src.taxonomy_core_entity import (
    HeadlessFlag,
    LifecycleEmitter,
    LifecycleGate,
    LifecycleState,
)
from modules.shared.src.taxonomy_core_error import (
    ResponseDetectionTimeoutError,
)
from modules.shared.src.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_GENERATION_FINISHED,
    EVENT_OUTPUT_COPIED,
    EVENT_PROMPT_INJECTED,
    EVENT_SEND_CLICKED,
    EVENT_STREAMING_GENERATION,
    EVENT_THINKING_STARTED,
    EVENT_WEB_LOADED,
    LifecycleEvent,
    QwenEventType,
)
from modules.shared.src.taxonomy_core_vo import (
    MessageCount,
    PollIntervalSec,
    PromptText,
    ResponseText,
    TimeoutSec,
)


class DirectPromptOrchestrator(IDirectPromptAggregate):
    """Orchestrates direct string text prompt execution."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        observability: IObservabilityProtocol,
    ) -> None:
        self._browser = browser
        self._injector = injector
        self._sender = sender
        self._streamer = streamer
        self._observability = observability

    def process_direct_prompt(
        self,
        prompt: PromptText | str,
        timeout_sec: TimeoutSec | int = 120,
        headless: HeadlessFlag | bool = True,
    ) -> ResponseText:
        """Pipeline 1: Process a direct text prompt string and return AI response."""
        try:
            prompt_str = str(prompt)
            fd, tmp_path = tempfile.mkstemp(suffix=".txt")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(prompt_str)

                cfg = build_app_config(
                    input_path=Path(tmp_path),
                    output_path=DEFAULT_OUTPUT,
                    headless=headless,
                )
                with self._browser.browser_session(cfg) as bctx:
                    page = bctx.pages[0] if bctx.pages else bctx.new_page()
                    text = self._execute_direct_on_page(
                        page, Path(tmp_path), prompt_str, int(timeout_sec), cfg
                    )
                return ResponseText(text)
            finally:
                p = Path(tmp_path)
                if p.exists():
                    p.unlink()
        except Exception as exc:
            return to_error_response(exc)

    def _execute_direct_on_page(
        self, page: Page, filepath: Path, prompt: str, timeout_sec: int, active_cfg: AppConfig
    ) -> str:
        logger = self._observability.get_logger()
        gate = LifecycleGate(logger)
        state = LifecycleState()
        emitter = LifecycleEmitter(logger, gate=gate)
        direct_prompt_events: tuple[QwenEventType, ...] = (
            EVENT_WEB_LOADED,
            EVENT_PROMPT_INJECTED,
            EVENT_SEND_CLICKED,
            EVENT_DISPATCH_ACKNOWLEDGED,
            EVENT_THINKING_STARTED,
            EVENT_STREAMING_GENERATION,
            EVENT_GENERATION_FINISHED,
            EVENT_OUTPUT_COPIED,
        )
        for event in direct_prompt_events:
            def _mark(_evt: LifecycleEvent, name: QwenEventType = event) -> None:
                state.mark(name)
            emitter.on(event, _mark)

        self._browser.navigate_to_chat(page, emitter)
        self._browser.check_auth(page)
        msg_count_before = self._sender.count_messages(page)

        try:
            baseline_response = latest_message_text(page)
        except Exception:
            baseline_response = None

        self._injector.inject_text(page, PromptText(prompt))
        emitter.emit(EVENT_PROMPT_INJECTED, {"file": str(filepath), "char_count": len(prompt)})

        self._sender.click_send(page, emitter, document_parsed=HeadlessFlag(True))
        if not state.dispatch_acknowledged:
            raise RuntimeError("Cannot wait for response: prompt dispatch is incomplete")

        stream_timeout_sec = min(timeout_sec, active_cfg.streaming_timeout)
        response = self._streamer.wait_for_response(
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


__all__ = ["DirectPromptOrchestrator"]
