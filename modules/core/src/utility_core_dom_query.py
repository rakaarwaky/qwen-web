"""DOM query utilities for Playwright pages.

Utility layer (utility_core_dom_query): stateless functions for DOM reading.
Consumed by SendDispatcher, StreamMonitor, and Agent.
Taxonomy constants + Playwright Page only.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Error, Page

from modules.shared.src.taxonomy_core_constant import (
    COMBINED_MESSAGE_SELECTOR,
    JS_COUNT_TURNS,
    JS_GET_RESPONSE_TEXT,
    RESPONSE_CONTENT_SELECTOR,
)
from modules.shared.src.taxonomy_core_vo import MessageCount, ResponseText


def count_messages(page: Page) -> MessageCount:
    """Count chat turns via injected JS with locator fallback.

    Tier 1: injected JS (JS_COUNT_TURNS) when it yields a positive int.
    Tier 2: combined message-selector locator count.
    Fallback: MessageCount(0).

    Returns
    -------
    MessageCount
        Number of message elements matching turn selectors.

    """
    try:
        count = page.evaluate(JS_COUNT_TURNS)
        if isinstance(count, int) and count > 0:
            return MessageCount(count)
    except Error:
        pass
    try:
        return MessageCount(page.locator(COMBINED_MESSAGE_SELECTOR).count())
    except Error:
        return MessageCount(0)


def latest_message_text(page: Page) -> ResponseText | None:
    """Extract the latest assistant response text via injected JS with locator fallback.

    Tier 1: injected JS (JS_GET_RESPONSE_TEXT) when it yields non-empty text.
    Tier 2: combined message-selector locator's last text content.
    Fallback: None.

    Returns
    -------
    ResponseText | None
        Trimmed text, or None when nothing is available.

    """
    try:
        text = page.evaluate(JS_GET_RESPONSE_TEXT)
        if text and isinstance(text, str) and len(text.strip()) > 0:
            return ResponseText(str(text.strip()))
    except Error:
        pass
    try:
        locator = page.locator(RESPONSE_CONTENT_SELECTOR)
        if locator.count() > 0:
            text = locator.last.text_content()
            if text is not None:
                return ResponseText(str(text.strip()))
    except Error:
        pass
    return None


def dispatch_and_wait_for_response(
    page: Page,
    injector: object,
    sender: object,
    streamer: object,
    emitter: object,
    state: object,
    logger: object,
    filepath: Path,
    prompt: str,
    msg_count_before: int,
    timeout_sec: int,
    active_cfg: object,
    sender_config: object | None = None,
    document_parsed: bool = True,
) -> str:
    """Inject prompt, click send, and wait for the AI response.

    Shared by the direct and file-only prompt orchestrators. ``injector``,
    ``sender``, ``streamer``, ``emitter``, ``state``, and ``logger`` are
    protocol/duck-typed collaborators passed by the caller (dependency
    injection) — this utility never imports capability or agent layers.
    """
    from modules.shared.src.taxonomy_core_error import ResponseDetectionTimeoutError
    from modules.shared.src.taxonomy_core_event import EVENT_PROMPT_INJECTED
    from modules.shared.src.taxonomy_core_vo import (
        HeadlessFlag,
        MessageCount,
        PollIntervalSec,
        PromptText,
        TimeoutSec,
    )

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
