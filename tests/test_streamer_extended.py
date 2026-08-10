"""Tests for streamer.py — remaining uncovered lines."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.streamer import validate_response_content
from src.types import LifecycleEmitter


class TestWaitForResponseExtended:
    def test_dispatch_not_acknowledged(self):
        from src.streamer import wait_for_response
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        with pytest.raises(RuntimeError, match="dispatch"):
            wait_for_response(page, 10, 0, emitter, dispatch_acknowledged=False)
