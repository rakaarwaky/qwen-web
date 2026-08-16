"""Agent: prompt file orchestrator (AES405).

Orchestrates prompt execution from local prompt file (.md) without attachment.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_config_factory import (
    build_app_config,
    resolve_pipeline_output_path,
)
from modules.core.src.utility_core_dom_query import latest_message_text
from modules.core.src.utility_core_error_mapping import to_error_response
from modules.core.src.utility_core_io_writer import save_orchestrator_output
from modules.shared.src.contract_core_aggregate import IPromptFileAggregate
from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
    IInjectionProtocol,
    IObservabilityProtocol,
    ISaverProtocol,
    ISendProtocol,
    IStreamProtocol,
)
from modules.shared.src.taxonomy_core_error import (
    ResponseDetectionTimeoutError,
)
from modules.shared.src.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_GENERATION_FINISHED,
    EVENT_LOGIN_VERIFIED,
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
    OutputPath,
    PollIntervalSec,
    PromptPath,
    PromptText,
    ResponseText,
    RunContext,
    TimeoutSec,
)


class PromptFileOrchestrator(IPromptFileAggregate):
    """Orchestrates prompt file execution (without document attachment)."""

    def __init__(
        self,
        browser: IBrowserProtocol,
        injector: IInjectionProtocol,
        sender: ISendProtocol,
        streamer: IStreamProtocol,
        saver: ISaverProtocol,
        observability: IObservabilityProtocol,
    ) -> None:
        self._browser = browser
        self._injector = injector
        self._sender = sender
        self._streamer = streamer
        self._saver = saver
        self._observability = observability

    def process_prompt_file_only(
        self,
        prompt_file: Path | PromptPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
    ) -> ResponseText:
        """Pipeline 2: Process a prompt file from disk without attachment."""
        try:
            p_path, out_path = resolve_pipeline_output_path(prompt_file, output_file)
            cfg = build_app_config(
                input_path=p_path,
                output_path=out_path,
                headless=headless,
            )
            ctx = RunContext()

            t0 = time.time()
            with self._browser.browser_session(cfg) as bctx:
                page = bctx.pages[0] if bctx.pages else bctx.new_page()
                text = self._execute_file_on_page(page, p_path, cfg.request_timeout, cfg)
            dur = time.time() - t0
            save_orchestrator_output(self._saver, out_path, p_path, text, dur, ctx)
            return ResponseText(f"Successfully processed {p_path.name} -> {out_path}")
        except Exception as exc:
            return to_error_response(exc)

    def _execute_file_on_page(self, page: Page, filepath: Path, timeout_sec: int, active_cfg: AppConfig) -> str:
        logger = self._observability.get_logger()
        file_prompt_events: tuple[QwenEventType, ...] = (
            EVENT_WEB_LOADED,
            EVENT_LOGIN_VERIFIED,
            EVENT_PROMPT_INJECTED,
            EVENT_SEND_CLICKED,
            EVENT_DISPATCH_ACKNOWLEDGED,
            EVENT_THINKING_STARTED,
            EVENT_STREAMING_GENERATION,
            EVENT_GENERATION_FINISHED,
            EVENT_OUTPUT_COPIED,
        )
        from modules.core.src.utility_core_dom_helper import setup_lifecycle_state

        emitter, state = setup_lifecycle_state(logger, file_prompt_events)

        prompt = filepath.read_text(encoding="utf-8").strip()

        self._browser.navigate_to_chat(page, emitter)
        self._browser.check_auth(page)
        msg_count_before = self._sender.count_messages(page)

        self._injector.find_input(page)

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


__all__ = ["PromptFileOrchestrator"]
