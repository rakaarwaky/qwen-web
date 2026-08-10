"""Tests for streamer.py — remaining uncovered lines in wait_for_response."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import Error as PlaywrightError

from src.streamer import wait_for_response
from src.types import (
    AuthRequiredError,
    LifecycleEmitter,
    NetworkTimeoutError,
    OutputValidationError,
)


class TestWaitForResponseExtended:
    def test_dispatch_not_acknowledged(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        with pytest.raises(RuntimeError, match="dispatch"):
            wait_for_response(page, 10, 0, emitter, dispatch_acknowledged=False)

    def test_timeout_returns_none(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        with patch("src.streamer.count_messages", return_value=0), \
             patch("src.streamer.latest_message_text", return_value=None), \
             patch("src.streamer.time") as mock_time:
            mock_time.time.return_value = 99999
            mock_time.sleep = MagicMock()
            result = wait_for_response(page, 1, 0, emitter)
            assert result is None

    def test_timeout_returns_text_when_present(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        text = "Valid AI response with enough content."

        with patch("src.streamer.count_messages", return_value=1), \
             patch("src.streamer.latest_message_text", return_value=text), \
             patch("src.streamer.time") as mock_time:
            mock_time.time.return_value = 99999
            mock_time.sleep = MagicMock()
            result = wait_for_response(page, 1, 0, emitter)
            assert result == text

    def test_auth_error_propagates(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)

        with patch("src.streamer.count_messages", side_effect=AuthRequiredError("login")), \
             patch("src.streamer.latest_message_text", return_value=None), \
             patch("src.streamer.time") as mock_time:
            mock_time.time.return_value = 99999
            mock_time.sleep = MagicMock()
            with pytest.raises(AuthRequiredError):
                wait_for_response(page, 1, 0, emitter)
