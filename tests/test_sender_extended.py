"""Tests for sender.py — remaining uncovered lines in click_send, count_messages, latest_message_text."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import Error as PlaywrightError

from modules.core.src.capabilities_send_dispatcher import click_send, count_messages, latest_message_text
from modules.shared.src import LifecycleEmitter, SendDispatchError


class TestClickSendExtended:
    def test_document_parsed_false_raises(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        with pytest.raises(SendDispatchError, match="document attachment parsing"):
            click_send(page, emitter, document_parsed=False)

    def test_selector_visible_but_disabled(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        loc = MagicMock()
        loc.count.return_value = 1
        loc.is_visible.return_value = True
        loc.is_enabled.return_value = False  # disabled

        def locator_factory(sel):
            return loc

        page.locator.side_effect = locator_factory

        # All selectors fail (disabled), Enter fallback also fails
        textarea = MagicMock()
        textarea.count.return_value = 0

        def locator_fallback(sel):
            if sel == "textarea.message-input-textarea":
                return textarea
            return loc

        page.locator.side_effect = locator_fallback

        with pytest.raises(SendDispatchError, match="Failed to send"):
            click_send(page, emitter)

    def test_selector_exception_continues(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        call_count = [0]
        def locator_factory(sel):
            call_count[0] += 1
            loc = MagicMock()
            if call_count[0] == 1:
                raise PlaywrightError("disconnected")
            loc.count.return_value = 1
            loc.is_visible.return_value = True
            loc.is_enabled.return_value = True
            return loc

        page.locator.side_effect = locator_factory
        click_send(page, emitter)
        emitter.emit.assert_called_once()


class TestCountMessagesExtended:
    def test_js_evaluate_returns_non_int(self):
        page = MagicMock()
        page.evaluate.return_value = "not_an_int"
        loc = MagicMock()
        loc.count.return_value = 0
        page.locator.return_value = loc
        result = count_messages(page)
        assert isinstance(result, int)

    def test_js_evaluate_exception_fallback(self):
        page = MagicMock()
        page.evaluate.side_effect = PlaywrightError("crashed")
        loc = MagicMock()
        loc.count.return_value = 3
        page.locator.return_value = loc
        result = count_messages(page)
        assert result == 3

    def test_both_methods_fail(self):
        page = MagicMock()
        page.evaluate.side_effect = PlaywrightError("crashed")
        page.locator.side_effect = PlaywrightError("crashed")
        result = count_messages(page)
        assert result == 0


class TestLatestMessageTextExtended:
    def test_js_returns_empty(self):
        page = MagicMock()
        page.evaluate.return_value = ""
        loc = MagicMock()
        loc.count.return_value = 0
        page.locator.return_value = loc
        result = latest_message_text(page)
        assert result is None

    def test_js_evaluate_exception_fallback(self):
        page = MagicMock()
        page.evaluate.side_effect = PlaywrightError("crashed")
        loc = MagicMock()
        loc.count.return_value = 1
        loc.last.text_content.return_value = "  answer  "
        page.locator.return_value = loc
        result = latest_message_text(page)
        assert result == "answer"

    def test_both_methods_fail(self):
        page = MagicMock()
        page.evaluate.side_effect = PlaywrightError("crashed")
        page.locator.side_effect = PlaywrightError("crashed")
        result = latest_message_text(page)
        assert result is None
