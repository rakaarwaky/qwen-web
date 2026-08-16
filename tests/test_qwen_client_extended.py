"""Tests for agent_core_orchestrator — send_file pipeline error paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import Error

from modules.core.src.agent_attachment_prompt_orchestrator import AttachmentPromptOrchestrator
from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.shared.src import (
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_DOCUMENT_PARSED,
    EVENT_FILE_UPLOADED,
    EVENT_GENERATION_FINISHED,
    EVENT_LOGIN_VERIFIED,
    EVENT_SEND_CLICKED,
    EVENT_STREAMING_GENERATION,
    EVENT_THINKING_STARTED,
    EVENT_WEB_LOADED,
    QwenCliError,
    ResponseDetectionTimeoutError,
    ResponseText,
)
from tests.helpers import make_test_orchestrator


def _make_attachment_orchestrator() -> AttachmentPromptOrchestrator:
    """Build an AttachmentPromptOrchestrator with all dependencies mocked."""
    return AttachmentPromptOrchestrator(
        browser=MagicMock(),
        injector=MagicMock(),
        sender=MagicMock(),
        streamer=MagicMock(),
        uploader=MagicMock(),
        saver=MagicMock(),
        observability=MagicMock(get_logger=MagicMock(return_value=MagicMock())),
    )


def _configure_lifecycle_mocks(orch) -> None:
    def navigate(_page, emitter):
        emitter.emit(EVENT_WEB_LOADED, {"url": "test"})
        emitter.emit(EVENT_LOGIN_VERIFIED, {"url": "test"})

    def upload(_page, _filepath, emitter=None, **_kwargs):
        assert emitter is not None
        emitter.emit(EVENT_FILE_UPLOADED, {"file": "test"})
        emitter.emit(EVENT_DOCUMENT_PARSED, {"file": "test"})
        return True

    def send(_page, emitter, **_kwargs):
        emitter.emit(EVENT_SEND_CLICKED, {"file": "test"})
        emitter.emit(EVENT_DISPATCH_ACKNOWLEDGED, {"file": "test"})

    orch._browser.navigate_to_chat.side_effect = navigate
    orch._browser.browser_session.return_value.__enter__.return_value.pages = [MagicMock()]
    orch._uploader.upload_attachment.side_effect = upload
    orch._sender.click_send.side_effect = send


class TestSendFile:
    def test_send_file_os_error(self, tmp_path):
        orch = _make_attachment_orchestrator()
        att = tmp_path / "att.md"
        att.write_text("attachment")
        result = orch.process_prompt_with_attachment(
            prompt_file=tmp_path / "nonexistent.md",
            attachment_file=att,
            output_file=tmp_path / "out.md",
            headless=True,
        )
        assert "ERROR" in str(result)

    def test_send_file_timeout_error(self, tmp_path):
        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)
        orch._sender.count_messages.return_value = 0
        orch._uploader.upload_attachment.return_value = True

        def timeout_stream(_page, _timeout, _before, emitter, **_kwargs):
            emitter.emit(EVENT_THINKING_STARTED)
            return None

        orch._streamer.wait_for_response.side_effect = timeout_stream

        f = tmp_path / "task.md"
        f.write_text("hello")
        att = tmp_path / "att.md"
        att.write_text("attachment")

        result = orch.process_prompt_with_attachment(
            prompt_file=f,
            attachment_file=att,
            output_file=tmp_path / "out.md",
            headless=True,
        )
        assert "Response detection timeout" in str(result)

    def test_send_file_delegates_to_capabilities(self, tmp_path):
        orch = _make_attachment_orchestrator()
        _configure_lifecycle_mocks(orch)
        orch._sender.count_messages.return_value = 2
        orch._uploader.upload_attachment.return_value = True

        def successful_stream(_page, _timeout, _before, emitter, **_kwargs):
            emitter.emit(EVENT_THINKING_STARTED)
            emitter.emit(EVENT_STREAMING_GENERATION, {"text_length": 12})
            emitter.emit(EVENT_GENERATION_FINISHED, {"text_length": 12})
            return "the response"

        orch._streamer.wait_for_response.side_effect = successful_stream

        f = tmp_path / "task.md"
        f.write_text("hello")
        att = tmp_path / "att.md"
        att.write_text("attachment")

        result = orch.process_prompt_with_attachment(
            prompt_file=f,
            attachment_file=att,
            output_file=tmp_path / "out.md",
            headless=True,
        )
        assert "Successfully processed" in str(result)
        orch._streamer.wait_for_response.assert_called_once()
        assert orch._streamer.wait_for_response.call_args[0][2] == 2

    def test_inject_text_types_with_delay_fallback(self):
        """Slow typing is delegated to inject_text's type() fallback."""
        page = MagicMock()
        page.evaluate.return_value = False
        el = MagicMock()
        el.fill.side_effect = Error("fill failed")
        injector = PromptInjector()
        with (
            patch.object(PromptInjector, "find_input", return_value=el),
            patch.object(PromptInjector, "_verify_injection", return_value=True),
        ):
            injector.inject_text(page, "text")
        el.type.assert_called_once_with("text", delay=10)
