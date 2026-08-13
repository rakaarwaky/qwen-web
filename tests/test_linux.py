"""Tests for linux.py — SingleInstanceLock, sd_notify."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from modules.core.src.capabilities_linux_guard import LinuxGuard, SingleInstanceLock
from modules.shared.src import SingleInstanceError


class TestSingleInstanceLock:
    def test_acquire_and_release(self, tmp_path):
        lock_path = tmp_path / "test.lock"
        with SingleInstanceLock(lock_path):
            assert lock_path.exists()

    def test_second_instance_raises(self, tmp_path):
        lock_path = tmp_path / "test.lock"
        with SingleInstanceLock(lock_path), pytest.raises(SingleInstanceError, match="already running"):
            with SingleInstanceLock(lock_path):
                pass

    def test_default_lock_path(self):
        with SingleInstanceLock():
            pass

    def test_context_manager_exit_cleans_up(self, tmp_path):
        lock_path = tmp_path / "test.lock"
        with SingleInstanceLock(lock_path):
            pass
        assert not lock_path.exists()


class TestSdNotify:
    def test_no_socket_returns(self):
        with patch.dict(os.environ, {}, clear=True):
            LinuxGuard()._sd_notify("READY=1")

    def test_with_socket(self, tmp_path):
        socket_path = str(tmp_path / "notify.sock")
        with patch.dict(os.environ, {"NOTIFY_SOCKET": socket_path}):
            LinuxGuard()._sd_notify("READY=1")

    def test_with_abstract_socket(self):
        with patch.dict(os.environ, {"NOTIFY_SOCKET": "@/test-abstract-socket"}):
            LinuxGuard()._sd_notify("READY=1")

    def test_unset_environment(self):
        with patch.dict(os.environ, {"NOTIFY_SOCKET": "/tmp/test", "WATCHDOG_USEC": "1", "WATCHDOG_PID": "1"}):
            LinuxGuard()._sd_notify("READY=1", unset_environment=True)
            assert "NOTIFY_SOCKET" not in os.environ

    def test_sd_notify_ready(self):
        with patch.dict(os.environ, {}, clear=True):
            LinuxGuard().sd_notify_ready()

    def test_sd_notify_stop(self):
        with patch.dict(os.environ, {}, clear=True):
            LinuxGuard().sd_notify_stop()

    def test_with_real_socket(self, tmp_path):
        import socket
        socket_path = str(tmp_path / "notify.sock")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.bind(socket_path)
        try:
            with patch.dict(os.environ, {"NOTIFY_SOCKET": socket_path}):
                LinuxGuard()._sd_notify("READY=1")
        finally:
            sock.close()

    def test_socket_connection_error(self):
        with patch.dict(os.environ, {"NOTIFY_SOCKET": "/nonexistent/socket"}):
            LinuxGuard()._sd_notify("READY=1")

    def test_unset_nonexistent_keys(self):
        with patch.dict(os.environ, {"NOTIFY_SOCKET": "/tmp/test"}):
            LinuxGuard()._sd_notify("READY=1", unset_environment=True)
