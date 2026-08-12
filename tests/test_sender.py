"""Unit tests for enterprise sender module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.core.src.capabilities_send_dispatcher import click_send, count_messages, latest_message_text
from modules.shared.src import LifecycleEmitter, SendDispatchError


def test_click_send_primary_selector_success():
    mock_page = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    mock_locator = MagicMock()
    mock_page.locator.return_value = mock_locator
    mock_locator.count.return_value = 1
    mock_locator.is_visible.return_value = True
    mock_locator.is_enabled.return_value = True

    click_send(mock_page, mock_emitter)

    mock_locator.click.assert_called_once()
    mock_emitter.emit.assert_called_once()


def test_click_send_enter_fallback():
    mock_page = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    # Primary selectors fail
    def locator_side_effect(sel):
        loc = MagicMock()
        if sel == "textarea.message-input-textarea":
            loc.count.return_value = 1
            return loc
        loc.count.return_value = 0
        return loc

    mock_page.locator.side_effect = locator_side_effect

    click_send(mock_page, mock_emitter)
    mock_emitter.emit.assert_called_once()


def test_click_send_all_failed():
    mock_page = MagicMock()
    mock_emitter = MagicMock(spec=LifecycleEmitter)

    mock_locator = MagicMock()
    mock_locator.count.return_value = 0
    mock_page.locator.return_value = mock_locator

    with pytest.raises(SendDispatchError, match="Failed to send"):
        click_send(mock_page, mock_emitter)


def test_count_messages():
    mock_page = MagicMock()
    mock_locator = MagicMock()
    mock_page.locator.return_value = mock_locator
    mock_locator.count.return_value = 3

    assert count_messages(mock_page) == 3


def test_latest_message_text():
    mock_page = MagicMock()
    mock_locator = MagicMock()
    mock_page.locator.return_value = mock_locator
    mock_locator.count.return_value = 1
    mock_locator.last.text_content.return_value = "  AI Answer  "

    assert latest_message_text(mock_page) == "AI Answer"
