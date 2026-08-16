"""Unit tests for DirectPromptOrchestrator (AES405)."""

from __future__ import annotations

from unittest.mock import MagicMock

from modules.core.src.agent_direct_prompt_orchestrator import DirectPromptOrchestrator
from modules.shared.src.taxonomy_core_error import ResponseDetectionTimeoutError
from modules.shared.src.taxonomy_core_event import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_GENERATION_FINISHED,
    EVENT_LOGIN_VERIFIED,
    EVENT_OUTPUT_COPIED,
    EVENT_SEND_CLICKED,
    EVENT_STREAMING_GENERATION,
    EVENT_THINKING_STARTED,
    EVENT_WEB_LOADED,
)


def _make_direct_orchestrator() -> tuple[DirectPromptOrchestrator, dict[str, MagicMock]]:
    browser = MagicMock()
    injector = MagicMock()
    sender = MagicMock()
    streamer = MagicMock()
    observability = MagicMock()
    observability.get_logger.return_value = MagicMock()

    orchestrator = DirectPromptOrchestrator(
        browser=browser,
        injector=injector,
        sender=sender,
        streamer=streamer,
        observability=observability,
    )
    mocks = {
        "browser": browser,
        "injector": injector,
        "sender": sender,
        "streamer": streamer,
        "observability": observability,
    }
    return orchestrator, mocks


def test_process_direct_prompt_happy_path() -> None:
    orch, mocks = _make_direct_orchestrator()

    page = MagicMock()
    page.url = "https://chat.qwen.ai/"
    bctx = MagicMock()
    bctx.pages = [page]
    mocks["browser"].browser_session.return_value.__enter__.return_value = bctx

    emitted_events: list[str] = []

    def navigate_stub(_p, emitter):
        emitted_events.append(str(EVENT_WEB_LOADED))
        emitter.emit(EVENT_WEB_LOADED, {"url": "test"})
        emitted_events.append(str(EVENT_LOGIN_VERIFIED))
        emitter.emit(EVENT_LOGIN_VERIFIED, {"url": "test"})

    mocks["browser"].navigate_to_chat.side_effect = navigate_stub

    def inject_stub(_p, _prompt):
        pass

    mocks["injector"].inject_text.side_effect = inject_stub

    def send_stub(_p, emitter, **_kwargs):
        emitted_events.append(str(EVENT_SEND_CLICKED))
        emitter.emit(EVENT_SEND_CLICKED)
        emitted_events.append(str(EVENT_DISPATCH_ACKNOWLEDGED))
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED)

    mocks["sender"].click_send.side_effect = send_stub

    def stream_stub(_p, _timeout, _count, emitter, **_kwargs):
        emitted_events.append(str(EVENT_THINKING_STARTED))
        emitter.emit(EVENT_THINKING_STARTED)
        emitted_events.append(str(EVENT_STREAMING_GENERATION))
        emitter.emit(EVENT_STREAMING_GENERATION)
        emitted_events.append(str(EVENT_GENERATION_FINISHED))
        emitter.emit(EVENT_GENERATION_FINISHED)
        emitted_events.append(str(EVENT_OUTPUT_COPIED))
        emitter.emit(EVENT_OUTPUT_COPIED)
        return "Hello from Qwen AI!"

    mocks["streamer"].wait_for_response.side_effect = stream_stub

    response = orch.process_direct_prompt("What is Python?", timeout_sec=30, headless=True)

    assert str(response) == "Hello from Qwen AI!"
    assert emitted_events == [
        "EVENT_WEB_LOADED",
        "EVENT_LOGIN_VERIFIED",
        "EVENT_SEND_CLICKED",
        "EVENT_DISPATCH_ACKNOWLEDGED",
        "EVENT_THINKING_STARTED",
        "EVENT_STREAMING_GENERATION",
        "EVENT_GENERATION_FINISHED",
        "EVENT_OUTPUT_COPIED",
    ]


def test_process_direct_prompt_timeout_error() -> None:
    orch, mocks = _make_direct_orchestrator()

    page = MagicMock()
    bctx = MagicMock()
    bctx.pages = [page]
    mocks["browser"].browser_session.return_value.__enter__.return_value = bctx

    def navigate_stub(_p, emitter):
        emitter.emit(EVENT_WEB_LOADED, {"url": "test"})
        emitter.emit(EVENT_LOGIN_VERIFIED, {"url": "test"})

    mocks["browser"].navigate_to_chat.side_effect = navigate_stub

    def send_stub(_p, emitter, **_kwargs):
        emitter.emit(EVENT_SEND_CLICKED)
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED)

    mocks["sender"].click_send.side_effect = send_stub
    mocks["streamer"].wait_for_response.side_effect = ResponseDetectionTimeoutError("Timeout waiting for response")

    response = orch.process_direct_prompt("Test prompt", timeout_sec=10)

    assert "Timeout waiting for response" in str(response)
