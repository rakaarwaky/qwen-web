"""Behavior-lock regression tests for the CoreOrchestrator send_file pipeline.

Exercises active CoreOrchestrator methods against headless Chromium + local
HTML fixture (tests/fixtures/qwen_fixture.html). Lock selectors, injection,
adaptive polling, and the send_file pipeline against regressions.

Run: python3 -m pytest tests/test_qwen_client_behavior.py -v
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.core.src.agent_core_orchestrator import CoreOrchestrator


def _make_orchestrator() -> CoreOrchestrator:
    """Build an orchestrator with real capabilities wired for fixture testing."""
    from modules.core.src.capabilities_audit_repository import AuditRepository
    from modules.core.src.capabilities_browser_adapter import BrowserAdapter
    from modules.core.src.capabilities_file_uploader import FileUploader
    from modules.core.src.capabilities_observability_setup import ObservabilitySetup
    from modules.core.src.capabilities_prompt_injector import PromptInjector
    from modules.core.src.capabilities_send_dispatcher import SendDispatcher
    from modules.core.src.capabilities_stream_monitor import StreamMonitor
    from pathlib import Path as _P

    return CoreOrchestrator(
        browser=BrowserAdapter(),
        injector=PromptInjector(),
        sender=SendDispatcher(),
        streamer=StreamMonitor(),
        uploader=FileUploader(),
        saver=MagicMock(),
        audit=AuditRepository(_P("/tmp/qwen-test-log")),
        observability=ObservabilitySetup(_P("/tmp/qwen-test-log")),
    )


def _probe_file(tmp_path: Path, content: str = "# probe\nconfirm you can read this file.\n") -> Path:
    p = tmp_path / "doc.md"
    p.write_text(content, encoding="utf-8")
    return p


class TestOrchestratorInit:
    def test_init_with_capabilities(self):
        orch = _make_orchestrator()
        assert orch._browser is not None
        assert orch._sender is not None

    def test_send_file_raises_without_browser(self, tmp_path):
        orch = CoreOrchestrator.__new__(CoreOrchestrator)
        orch._emitter = lambda: MagicMock()
        probe = _probe_file(tmp_path)
        with pytest.raises(Exception):
            orch.send_file(None, probe, timeout_sec=5)  # type: ignore[arg-type]


class TestResetPage:
    def test_reset_page_navigates_to_chat_url(self, client, page, monkeypatch):
        navigated = []

        def stub_goto(url, **kwargs):
            navigated.append(url)

        monkeypatch.setattr(page, "goto", stub_goto)
        monkeypatch.setattr(page, "wait_for_load_state", lambda *a, **k: None)
        client._browser.reset_page(page, client._emitter())
        assert navigated == ["https://chat.qwen.ai/"]


class TestTypeSlowly:
    def test_type_slowly_inputs_text(self, client, page):
        textarea = page.query_selector(".message-input-textarea")
        assert textarea is not None
        client._type_slowly(page, textarea, "slow text")
        val = page.evaluate("e => e.value", textarea)
        assert val == "slow text"


class TestWaitForResponse:
    def test_waits_for_new_message(self, client, page, monkeypatch):
        # Simulate a new assistant message appearing after 500ms
        page.evaluate("""() => {
            setTimeout(() => {
                const log = document.getElementById('chatLog');
                const reply = document.createElement('div');
                reply.className = 'assistant';
                const mb = document.createElement('div');
                mb.className = 'markdown-body';
                mb.textContent = 'This is the assistant response.';
                reply.appendChild(mb);
                log.appendChild(reply);
            }, 500);
        }""")

        # Count messages before
        msg_count_before = client._count_messages(page)

        response = client._wait_for_response(page, timeout_sec=5, msg_count_before=msg_count_before)
        assert response is not None
        assert "assistant response" in response

    def test_returns_none_on_timeout(self, client, page, monkeypatch):
        # No message will appear — should timeout
        msg_count_before = client._count_messages(page)
        response = client._wait_for_response(page, timeout_sec=1, msg_count_before=msg_count_before)
        assert response is None

    def test_returns_stable_text(self, client, page, monkeypatch):
        # Capture baseline count, then simulate a new message appearing
        msg_count_before = client._count_messages(page)

        page.evaluate("""() => {
            setTimeout(() => {
                const log = document.getElementById('chatLog');
                const reply = document.createElement('div');
                reply.className = 'assistant';
                const mb = document.createElement('div');
                mb.className = 'markdown-body';
                mb.textContent = 'Already present message.';
                reply.appendChild(mb);
                log.appendChild(reply);
            }, 500);
        }""")

        response = client._wait_for_response(page, timeout_sec=5, msg_count_before=msg_count_before)
        assert response == "Already present message."


class TestSendFilePipeline:
    def test_send_file_raises_when_no_page(self, tmp_path):
        orch = _make_orchestrator()
        probe = _probe_file(tmp_path)
        with pytest.raises(Exception):
            orch.send_file(None, probe, timeout_sec=5)  # type: ignore[arg-type]

    def test_send_file_full_flow(self, client, page, tmp_path, monkeypatch):
        monkeypatch.setattr(page, "goto", lambda *a, **k: None)

        probe = _probe_file(tmp_path)
        res = client.send_file(page, probe, timeout_sec=5)
        assert "received the attached file" in res.lower()

    def test_send_file_with_custom_prompt_role(self, client, page, tmp_path, monkeypatch):
        monkeypatch.setattr(page, "goto", lambda *a, **k: None)

        probe = _probe_file(tmp_path, "Task prompt content")
        role_prompt = tmp_path / "PROMPT.md"
        role_prompt.write_text("---\nrole: arch\n---\nSystem role instructions.", encoding="utf-8")

        res = client.send_file(page, probe, timeout_sec=5, custom_prompt_path=role_prompt)
        assert "received the attached file" in res.lower()

    def test_send_file_raises_timeout_when_no_response(self, client, page, tmp_path, monkeypatch):
        monkeypatch.setattr(page, "goto", lambda *a, **k: None)
        monkeypatch.setattr(client._streamer, "wait_for_response", lambda *a, **k: None)

        probe = _probe_file(tmp_path)
        with pytest.raises(TimeoutError, match="Timeout after"):
            client.send_file(page, probe, timeout_sec=1)
