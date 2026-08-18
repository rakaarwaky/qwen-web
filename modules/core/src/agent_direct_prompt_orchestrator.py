"""Agent: direct text prompt orchestrator (AES405).

Orchestrates direct string text prompt execution without prompt file on disk.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from playwright.sync_api import Page

from modules.core.src.utility_core_agent_helper import execute_direct_on_page
from modules.core.src.utility_core_config_factory import build_app_config, resolve_pipeline_output_path
from modules.core.src.utility_core_error_mapping import to_error_response
from modules.core.src.utility_core_io_writer import save_orchestrator_output
from modules.shared.src.contract_core_aggregate import IDirectPromptAggregate
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
    OutputPath,
    PollIntervalSec,
    PromptText,
    ResponseText,
    RunContext,
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
        saver: ISaverProtocol,
        observability: IObservabilityProtocol,
    ) -> None:
        self._browser = browser
        self._injector = injector
        self._sender = sender
        self._streamer = streamer
        self._saver = saver
        self._observability = observability

    def process_direct_prompt(
        self,
        prompt: PromptText | str,
        timeout_sec: TimeoutSec | int = 120,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag | bool = True,
    ) -> ResponseText:
        """Pipeline 1: Process a direct text prompt string and return AI response."""
        try:
            prompt_str = str(prompt)
            fd, tmp_path = tempfile.mkstemp(suffix=".txt")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(prompt_str)

                p_path, out_path = resolve_pipeline_output_path(Path(tmp_path), output_file)
                cfg = build_app_config(
                    input_path=p_path,
                    output_path=out_path,
                    headless=headless,
                )
                ctx = RunContext()
                t0 = time.time()
                with self._browser.browser_session(cfg) as bctx:
                    page = bctx.pages[0] if bctx.pages else bctx.new_page()
                    text = execute_direct_on_page(page, p_path, prompt_str, int(timeout_sec), cfg)
                dur = time.time() - t0
                save_orchestrator_output(self._saver, out_path, p_path, text, dur, ctx)
                return ResponseText(text)
            finally:
                p = Path(tmp_path)
                if p.exists():
                    p.unlink()
        except Exception as exc:
            return to_error_response(exc)


__all__ = ["DirectPromptOrchestrator"]
