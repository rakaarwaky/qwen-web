"""Unit tests for enterprise sender module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.utility_core_dom_query import count_messages, latest_message_text
from modules.shared.src import LifecycleEmitter, SendDispatchError


def _sender() -> SendDispatcher:
    return SendDispatcher()


def test_click_send_primary_selector_success():
    mock_page = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    mock_locator = MagicMock()
    mock_page.locator.return_value = mock_locator
    mock_locator.count.return_value = 1
    mock_locator.first.is_visible.return_value = True
    mock_locator.is_enabled.return_value = True

    _sender().click_send(mock_page, mock_emitter)

    mock_locator.first.click.assert_called_once()
    mock_emitter.emit.assert_called_once()


def test_click_send_enter_fallback():
    mock_page = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    # Primary selectors fail (nothing visible)
    def locator_side_effect(sel):
        loc = MagicMock()
        loc.count.return_value = 0
        loc.first.is_visible.return_value = False
        return loc

    mock_page.locator.side_effect = locator_side_effect

    _sender().click_send(mock_page, mock_emitter)
    mock_page.keyboard.press.assert_called_once_with("Enter")
    mock_emitter.emit.assert_called_once()


def test_click_send_all_failed():
    mock_page = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    mock_locator = MagicMock()
    mock_locator.count.return_value = 0
    mock_locator.first.is_visible.return_value = False
    mock_page.locator.return_value = mock_locator

    # No visible selector and Enter fails — click_send must not raise
    mock_page.keyboard.press.side_effect = Exception("no textarea")
    _sender().click_send(mock_page, mock_emitter)
    mock_page.keyboard.press.assert_called_once()


def test_count_messages():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = 3

    assert count_messages(mock_page) == 3


def test_latest_message_text():
    mock_page = MagicMock()
    mock_page.evaluate.return_value = "  AI Answer  "

    assert latest_message_text(mock_page) == "AI Answer"