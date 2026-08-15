"""Agent: prompt file orchestrator (AES405).

Orchestrates prompt execution from local prompt file (.md) without attachment.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_config_factory import build_app_config
from modules.core.src.utility_core_dom_query import latest_message_text
from modules.core.src.utility_core_error_mapping import to_error_response
from modules.shared.src.contract_core_aggregate import IPromptFileAggregate
from modules.shared.src.contract_core_protocol import (
    IBrowserProtocol,
    IInjectionProtocol,
    IObservabilityProtocol,
    ISaverProtocol,
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
    EVENT_DOCUMENT_PARSED,
    EVENT_FILE_UPLOADED,
    EVENT_PROMPT_INJECTED,
    PIPELINE_EVENT_SEQUENCE,
    LifecycleEvent,
    QwenEventType,
)
from modules.shared.src.taxonomy_core_vo import (
    FilePath,
    MessageCount,
    OutputChars,
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
            p_path = Path(prompt_file).resolve()
            if not p_path.exists():
                raise FileNotFoundError(f"Input file not found: {p_path}")

            out_path = Path(output_file).resolve() if output_file else DEFAULT_OUTPUT / p_path.name
            if out_path.is_dir():
                out_path = out_path / f"{p_path.stem}_output.md"

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
            prompt_len = p_path.stat().st_size if p_path.exists() else 0
            self._saver.write_output(
                out_path,
                ResponseText(text),
                ctx,
                FilePath(str(p_path)),
                dur,
                prompt_len,
                OutputChars(len(text)),
            )
            return ResponseText(f"Successfully processed {p_path.name} -> {out_path}")
        except Exception as exc:
            return to_error_response(exc)

    def _execute_file_on_page(
        self, page: Page, filepath: Path, timeout_sec: int, active_cfg: AppConfig
    ) -> str:
        logger = self._observability.get_logger()
        gate = LifecycleGate(logger)
        state = LifecycleState()
        emitter = LifecycleEmitter(logger, gate=gate)
        for event in PIPELINE_EVENT_SEQUENCE:
            def _mark(_evt: LifecycleEvent, name: QwenEventType = event) -> None:
                state.mark(name)
            emitter.on(event, _mark)

        prompt = filepath.read_text(encoding="utf-8").strip()

        self._browser.navigate_to_chat(page, emitter)
        self._browser.check_auth(page)
        msg_count_before = self._sender.count_messages(page)

        self._injector.find_input(page)
        emitter.emit(EVENT_FILE_UPLOADED, {"file": "none"})
        emitter.emit(EVENT_DOCUMENT_PARSED, {"file": "none"})

        try:
            baseline_response = latest_message_text(page)
        except Exception:
            baseline_response = None

        self._injector.inject_text(page, PromptText(prompt))
        emitter.emit(EVENT_PROMPT_INJECTED, {"file": str(filepath), "char_count": len(prompt)})

        self._sender.click_send(page, emitter, document_parsed=HeadlessFlag(state.document_parsed))
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
