"""Tests for streamer.py — remaining uncovered lines."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.core.src.capabilities_stream_monitor import validate_response_content
from modules.shared.src import LifecycleEmitter


class TestWaitForResponseExtended:
    def test_dispatch_not_acknowledged(self):
        from modules.core.src.capabilities_stream_monitor import wait_for_response
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        with pytest.raises(RuntimeError, match="dispatch"):
            wait_for_response(page, 10, 0, emitter, dispatch_acknowledged=False)
