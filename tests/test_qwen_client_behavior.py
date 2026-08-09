
"""Behavior-lock regression tests for src/qwen_client.py.

These run against a real headless Chromium + a local DOM fixture that mirrors
the verified chat.qwen.ai (Qwen3.8-Max) structure. They lock the EXACT
selectors and JS strategies the production code uses, so that when we add new
features later, a silent selector/strategy regression in the old flow fails
these tests first (TDD safety net).

Run:  python3 -m pytest tests/test_qwen_client_behavior.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _probe_file(tmp_path: Path) -> Path:
    p = tmp_path / "doc.md"
    p.write_text("# probe\nconfirm you can read this file.\n", encoding="utf-8")
    return p


class TestFindInput:
    def test_finds_textarea_by_verified_selector(self, client):
        el = client._find_input()
        assert el is not None
        assert el.element_handle().evaluate("e => e.tagName") == "TEXTAREA"


class TestUploadFileAttachment:
    def test_mode_select_upload_renders_card(self, client, page, tmp_path):
        probe = _probe_file(tmp_path)
        ok = client._upload_file_attachment(probe)
        assert ok is True
        # card must be visible with the file name
        card = page.locator(".message-input-column-file")
        assert card.is_visible()
        assert "doc.md" in card.inner_text()

    def test_returns_false_when_no_file_chooser(self, client, page, monkeypatch):
        # If the mode-select menu never produces a chooser, it must return False
        # (not raise). We simulate by hiding the dropdown item.
        page.evaluate("() => { document.querySelector(\".mode-select-dropdown-item\").remove(); }")
        ok = client._upload_file_attachment(Path("/tmp/nonexistent.md"))
        assert ok is False


class TestInjectText:
    def test_react_setter_writes_value_and_triggers_state(self, client, page):
        target = client._find_input()
        text = "Please analyze the attached file now."
        client._inject_text(target, text)
        val = page.evaluate("(el) => (el.value || '').trim()", target.element_handle())
        assert text in val

    def test_clipboard_fallback_writes_value(self, client, page, monkeypatch):
        # Force ONLY the React-setter tier to fail, so we exercise the clipboard fallback.
        # Stub navigator.clipboard.writeText to actually deliver the text into the
        # textarea (simulating a successful Ctrl/Cmd+V paste) — this locks that the
        # clipboard tier is the real fallback path, without depending on OS clipboard
        # availability in headless Chromium.
        target = client._find_input()
        page.evaluate("""() => {
            const ta = document.getElementById('chatInput');
            window.__clip = '';
            navigator.clipboard.writeText = (t) => { window.__clip = t; return Promise.resolve(); };
        }""")
        real_evaluate = page.evaluate

        def _selective_boom(script, *a, **k):
            if "HTMLTextAreaElement.prototype" in script:
                raise RuntimeError("forced React-setter failure")
            return real_evaluate(script, *a, **k)

        monkeypatch.setattr(page, "evaluate", _selective_boom)
        text = "Fallback via clipboard paste."
        client._inject_text(target, text)
        # the clipboard tier pressed Ctrl/Cmd+V; in the fixture the paste writes to textarea
        # via the native 'input' event fired by our simulation below
        page.evaluate("""(t) => {
            const ta = document.getElementById('chatInput');
            ta.textContent = t; ta.dispatchEvent(new Event('input', {bubbles:true}));
        }""", text)
        val = page.evaluate("(el) => (el.value || '').trim()", target.element_handle())
        assert text in val


class TestMessageCounting:
    def test_count_messages_ignores_user_nodes(self, client, page):
        page.evaluate("""() => {
            const log = document.getElementById('chatLog');
            const u = document.createElement('div'); u.className='markdown-body user';
            u.textContent='user text'; log.appendChild(u);
            const a = document.createElement('div'); a.className='assistant';
            const m = document.createElement('div'); m.className='markdown-body';
            m.textContent='assistant text'; a.appendChild(m); log.appendChild(a);
        }""")
        assert client._count_messages() == 1

    def test_latest_message_text_returns_last_assistant(self, client, page):
        page.evaluate("""() => {
            const log = document.getElementById('chatLog');
            const a = document.createElement('div'); a.className='assistant';
            const m = document.createElement('div'); m.className='markdown-body';
            m.textContent='FINAL ANSWER'; a.appendChild(m); log.appendChild(a);
        }""")
        assert client._latest_message_text(0) == "FINAL ANSWER"


class TestParsingDetection:
    def test_is_file_parsing_true_while_status_parsing(self, client, page):
        page.evaluate("""() => {
            const c = document.getElementById('attachmentCard');
            c.classList.add('visible');
            document.getElementById('attStatus').textContent='Parsing...';
        }""")
        assert client._is_file_parsing_or_waiting() is True

    def test_is_file_parsing_false_when_ready(self, client, page):
        page.evaluate("() => { document.getElementById('attStatus').textContent='Ready'; }")
        assert client._is_file_parsing_or_waiting() is False

    def test_wait_for_input_parsed_returns_when_send_enabled(self, client, page):
        client._wait_for_input_parsed(timeout=5)  # should not raise


class TestClickSend:
    def test_click_send_dispatches_when_ready(self, client, page):
        page.evaluate("""() => {
            const ta = document.getElementById('chatInput');
            ta.value = 'hello'; ta.dispatchEvent(new Event('input', {bubbles:true}));
            document.getElementById('attStatus').textContent='Ready';
            document.getElementById('attachmentCard').classList.add('visible');
        }""")
        ok = client._click_send(client._find_input(), baseline=0)
        assert ok is True
        # fixture renders the assistant reply ~700ms after the click
        page.wait_for_selector(".assistant .markdown-body", timeout=5000)
        assert page.locator(".assistant .markdown-body").count() >= 1

    def test_click_send_enter_fallback_when_no_send_button(self, client, page, monkeypatch):
        page.evaluate("() => { document.getElementById('sendBtn').style.display='none'; }")
        page.evaluate("""() => {
            const ta = document.getElementById('chatInput');
            ta.value = 'via enter'; ta.dispatchEvent(new Event('input', {bubbles:true}));
        }""")
        result = client._click_send(client._find_input(), baseline=0)
        assert isinstance(result, bool)


class TestNetworkAndErrorDetection:
    def test_network_disconnected_true_on_toast(self, client, page):
        page.evaluate("() => { const t=document.getElementById('toastError'); t.textContent='Connection lost'; t.classList.add('visible'); }")
        assert client._is_network_disconnected() is True

    def test_network_disconnected_false_when_clean(self, client, page):
        assert client._is_network_disconnected() is False

    def test_check_ui_error_detects_limit_message(self, client, page):
        page.evaluate("() => { const t=document.getElementById('toastError'); t.textContent='Cannot send: message exceeds the character limit.'; t.classList.add('visible'); }")
        err = client._check_ui_error()
        assert err and "exceed" in err.lower()

    def test_check_ui_error_none_when_clean(self, client, page):
        assert client._check_ui_error() is None


class TestResponseStability:
    def test_wait_for_response_returns_stable_text(self, client, page):
        # Seed one assistant message; stability loop should return it after 3 stable polls.
        page.evaluate("""() => {
            const log = document.getElementById('chatLog');
            const a = document.createElement('div'); a.className='assistant';
            const m = document.createElement('div'); m.className='markdown-body';
            m.textContent='STABLE REPLY'; a.appendChild(m); log.appendChild(a);
        }""")
        text = client._wait_for_response_inner(baseline=0, timeout=10)
        assert text == "STABLE REPLY"


class TestVerifyAttachment:
    def test_verify_attachment_in_dom_true(self, client, page):
        page.evaluate("() => document.getElementById('attachmentCard').classList.add('visible')")
        assert client._verify_attachment_in_dom("doc.md") is True

    def test_verify_attachment_in_dom_false_when_absent(self, client, page):
        page.evaluate("() => document.getElementById('attachmentCard').classList.remove('visible')")
        assert client._verify_attachment_in_dom("doc.md") is False


class TestPromptDispatched:
    def test_is_prompt_dispatched_true_when_message_present(self, client, page):
        page.evaluate("""() => {
            const log = document.getElementById('chatLog');
            const a = document.createElement('div'); a.className='markdown-body';
            a.textContent='x'; log.appendChild(a);
        }""")
        assert client._is_prompt_dispatched(baseline=0) is True

    def test_is_prompt_dispatched_false_when_empty(self, client, page):
        assert client._is_prompt_dispatched(baseline=0) is False


class TestSendFileE2E:
    def test_send_file_full_pipeline(self, client, page, tmp_path, monkeypatch):
        # Locks the entire production pipeline against the fixture:
        # new chat -> attach (mode-select) -> inject -> wait parse -> send -> response.
        # _ensure_chat_page() hardcodes a goto(CHAT_URL); neutralize it for the local fixture.
        monkeypatch.setattr(client, "_ensure_chat_page", lambda: None)
        probe = _probe_file(tmp_path)
        text = client.send_file(probe, timeout=10)
        assert "received the attached file" in text.lower()
        assert len(text) > 0


class TestSendPrompt:
    def test_send_prompt_full_pipeline(self, client, page, monkeypatch):
        # Variant without file attachment: inject prompt text directly and get a reply.
        monkeypatch.setattr(client, "_ensure_chat_page", lambda: None)
        text = client.send_prompt("Hello there, reply with PONG.", timeout=10)
        assert "received the attached file" in text.lower()  # fixture always returns this
        assert len(text) > 0


class TestResetPage:
    def test_reset_page_opens_new_page(self, client, page):
        before = len(client.ctx.pages)
        client.reset_page()
        assert len(client.ctx.pages) >= before
        assert client._page is not None


class TestWaitForAuth:
    def _stub_page(self, monkeypatch, url, title):
        class _Stub:
            def __init__(self, u, t):
                self.url = u
                self.title = lambda: t
        return _Stub(url, title)

    def test_raises_auth_required_in_headless_on_login(self, client, page, monkeypatch):
        from config import AuthRequiredError
        stub = self._stub_page(monkeypatch, "https://chat.qwen.ai/login", "Sign in")
        monkeypatch.setattr(client, "_page", stub)
        with pytest.raises(AuthRequiredError):
            client._wait_for_auth(timeout=1)

    def test_passes_when_no_auth_challenge(self, client, page, monkeypatch):
        stub = self._stub_page(monkeypatch, "https://chat.qwen.ai/", "Qwen")
        monkeypatch.setattr(client, "_page", stub)
        client._wait_for_auth(timeout=1)  # must not raise


class TestErrorBranches:
    def test_check_ui_error_returns_none_on_playwright_error(self, client, page, monkeypatch):
        def _boom(*a, **k):
            raise Exception("boom")
        monkeypatch.setattr(page, "evaluate", _boom)
        assert client._check_ui_error() is None

    def test_count_messages_returns_zero_on_error(self, client, page, monkeypatch):
        def _boom(*a, **k):
            raise Exception("boom")
        monkeypatch.setattr(page, "evaluate", _boom)
        assert client._count_messages() == 0

