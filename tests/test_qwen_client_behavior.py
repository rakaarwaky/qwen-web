"""Behavior-lock regression tests for P7 src/qwen_client.py.

Exercises active QwenClient methods against headless Chromium + local HTML fixture
(tests/fixtures/qwen_fixture.html). Lock selectors, MutationObserver injection,
adaptive polling, and send_file pipeline against regressions.

Run: python3 -m pytest tests/test_qwen_client_behavior.py -v
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.qwen_client import QwenClient


def _probe_file(tmp_path: Path, content: str = "# probe\nconfirm you can read this file.\n") -> Path:
    p = tmp_path / "doc.md"
    p.write_text(content, encoding="utf-8")
    return p


class TestQwenClientInit:
    def test_init_with_ctx(self, browser_ctx):
        client = QwenClient(browser_ctx)
        assert client.context is browser_ctx
        assert client.page is not None

    def test_init_without_ctx(self):
        client = QwenClient(None)
        assert client.context is None
        assert client.page is None


class TestResetPage:
    def test_reset_page_navigates_to_chat_url(self, client, page, monkeypatch):
        navigated = []

        def stub_goto(url, **kwargs):
            navigated.append(url)

        monkeypatch.setattr(page, "goto", stub_goto)
        monkeypatch.setattr(page, "wait_for_load_state", lambda *a, **k: None)
        client.reset_page()
        assert navigated == ["https://chat.qwen.ai/"]


class TestTypeSlowly:
    def test_type_slowly_inputs_text(self, client, page):
        textarea = page.query_selector(".message-input-textarea")
        assert textarea is not None
        client._type_slowly(textarea, "slow text")
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
        msg_count_before = client._count_messages()

        response = client._wait_for_response(timeout_sec=5, msg_count_before=msg_count_before)
        assert response is not None
        assert "assistant response" in response

    def test_raises_timeout_error_on_timeout(self, client, page, monkeypatch):
        # No message will appear — should raise TimeoutError
        msg_count_before = client._count_messages()
        with pytest.raises(TimeoutError, match="Timeout after"):
            client._wait_for_response(timeout_sec=1, msg_count_before=msg_count_before)

    def test_returns_stable_text(self, client, page, monkeypatch):
        # Capture baseline count, then simulate a new message appearing
        msg_count_before = client._count_messages()

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

        response = client._wait_for_response(timeout_sec=5, msg_count_before=msg_count_before)
        assert response == "Already present message."


class TestSendFilePipeline:
    def test_send_file_raises_when_no_page(self, tmp_path):
        client = QwenClient(None)
        probe = _probe_file(tmp_path)
        with pytest.raises(RuntimeError, match="Browser not started"):
            client.send_file(probe, timeout_sec=5)

    def test_send_file_full_flow(self, client, page, tmp_path, monkeypatch):
        monkeypatch.setattr(client, "reset_page", lambda: None)
        monkeypatch.setattr(page, "goto", lambda *a, **k: None)

        probe = _probe_file(tmp_path)
        res = client.send_file(probe, timeout_sec=5)
        assert "received the attached file" in res.lower()

    def test_send_file_with_custom_prompt_role(self, client, page, tmp_path, monkeypatch):
        monkeypatch.setattr(client, "reset_page", lambda: None)
        monkeypatch.setattr(page, "goto", lambda *a, **k: None)

        probe = _probe_file(tmp_path, "Task prompt content")
        role_prompt = tmp_path / "PROMPT.md"
        role_prompt.write_text("---\nrole: arch\n---\nSystem role instructions.", encoding="utf-8")

        res = client.send_file(probe, timeout_sec=5, custom_prompt_path=role_prompt)
        assert "received the attached file" in res.lower()

    def test_send_file_raises_timeout_when_no_response(self, client, page, tmp_path, monkeypatch):
        monkeypatch.setattr(client, "reset_page", lambda: None)
        monkeypatch.setattr(page, "goto", lambda *a, **k: None)
        monkeypatch.setattr(client, "_wait_for_response", lambda t, c: None)

        probe = _probe_file(tmp_path)
        with pytest.raises(TimeoutError, match="Timeout after"):
            client.send_file(probe, timeout_sec=1)


class TestClientLifecycle:
    def test_stop_is_noop(self):
        mock_ctx = MagicMock()
        client = QwenClient(mock_ctx)
        client.stop()
        mock_ctx.close.assert_not_called()

    def test_context_manager(self, monkeypatch):
        mock_start = MagicMock()
        mock_stop = MagicMock()
        monkeypatch.setattr(QwenClient, "start", mock_start)
        monkeypatch.setattr(QwenClient, "stop", mock_stop)

        client = QwenClient(None)
        with client as c:
            assert c is client
            mock_start.assert_called_once()
        mock_stop.assert_called_once()
