"""Tests for streamer.py — remaining uncovered lines."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from modules.core.src.capabilities_stream_monitor import StreamMonitor, validate_response_content
from modules.shared.src import LifecycleEmitter


class TestWaitForResponseExtended:
    def test_dispatch_not_acknowledged(self):
        page = MagicMock()
        emitter = MagicMock(spec=LifecycleEmitter)
        with pytest.raises(RuntimeError, match="dispatch"):
            StreamMonitor().wait_for_response(page, 10, 0, emitter, dispatch_acknowledged=False)
