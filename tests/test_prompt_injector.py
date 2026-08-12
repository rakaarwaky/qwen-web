"""Unit tests for enterprise prompt_injector module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from playwright.sync_api import Error
from playwright.sync_api import TimeoutError

from modules.core.src.capabilities_prompt_injector import find_input, inject_text, type_slowly
from modules.shared.src import (
    ElementNotFoundError,
    PromptInjectionError,
)


def test_find_input_success():
    mock_page = MagicMock()
    mock_el = MagicMock()
    mock_page.wait_for_selector.return_value = mock_el

    el = find_input(mock_page)
    assert el == mock_el


def test_find_input_timeout():
    mock_page = MagicMock()
    mock_page.wait_for_selector.side_effect = TimeoutError("Selector timeout")

    with pytest.raises(ElementNotFoundError, match="Timed out waiting for input selector"):
        find_input(mock_page)


def test_inject_text_empty():
    mock_page = MagicMock()
    with pytest.raises(PromptInjectionError, match="Cannot inject empty"):
        inject_text(mock_page, "")


def test_inject_text_react_strategy_success():
    mock_page = MagicMock()
    mock_el = MagicMock()
    mock_page.wait_for_selector.return_value = mock_el
    mock_page.evaluate.side_effect = [True, True]  # JS evaluate success, verification success

    inject_text(mock_page, "Hello Qwen")
    assert mock_page.evaluate.call_count >= 1


def test_inject_text_fallback_to_fill():
    mock_page = MagicMock()
    mock_el = MagicMock()
    mock_page.wait_for_selector.return_value = mock_el
    # React and contenteditable evaluate return False or fail, fall back to fill()
    mock_page.evaluate.side_effect = [False, False, True]

    inject_text(mock_page, "Hello Qwen with fill")
    mock_el.fill.assert_called_once_with("Hello Qwen with fill")


def test_type_slowly_success():
    mock_page = MagicMock()
    mock_el = MagicMock()

    type_slowly(mock_page, mock_el, "slow text", delay_ms=15)
    mock_el.type.assert_called_once_with("slow text", delay=15)


def test_type_slowly_failure():
    mock_page = MagicMock()
    mock_el = MagicMock()
    mock_el.type.side_effect = Error("Typing error")

    with pytest.raises(PromptInjectionError, match="Native typing failed"):
        type_slowly(mock_page, mock_el, "slow text")
