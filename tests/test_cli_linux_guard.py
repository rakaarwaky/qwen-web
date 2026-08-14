from __future__ import annotations

import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from modules import root_mcp_main_entry
from modules.core.src.capabilities_linux_guard import LinuxGuard
from modules.root_cli_main_entry import _run_cli_lifecycle, main
from modules.shared.src import SingleInstanceError


class TestCliLinuxLifecycle:
    def test_ready_then_stopping_and_release_after_dispatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lock_path = tmp_path / "qwen.lock"
        notify_path = tmp_path / "notify.sock"
        receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        receiver.bind(str(notify_path))
        receiver.settimeout(1)
        monkeypatch.setenv("NOTIFY_SOCKET", str(notify_path))
        container = SimpleNamespace(linux=LinuxGuard(lock_path), core=object())

        try:
            with patch("modules.root_cli_main_entry._default_container", return_value=container):
                result = _run_cli_lifecycle(lambda _container: 7)
            assert result == 7
            assert receiver.recv(64) == b"READY=1"
            assert receiver.recv(64) == b"STOPPING=1"
            assert not lock_path.exists()
        finally:
            receiver.close()

    def test_cleanup_after_dispatch_exception(self, tmp_path: Path) -> None:
        events: list[str] = []

        class FakeLinux:
            def acquire_lock(self) -> object:
                events.append("acquire")
                return object()

            def sd_notify_ready(self) -> None:
                events.append("ready")

            def sd_notify_stop(self) -> None:
                events.append("stop")

            def release_lock(self, _lock: object) -> None:
                events.append("release")

        container = SimpleNamespace(linux=FakeLinux(), core=object())
        with (
            patch("modules.root_cli_main_entry._default_container", return_value=container),
            pytest.raises(RuntimeError, match="boom"),
        ):
            _run_cli_lifecycle(lambda _container: (_ for _ in ()).throw(RuntimeError("boom")))
        assert events == ["acquire", "ready", "stop", "release"]

    def test_second_instance_is_rejected(self, tmp_path: Path) -> None:
        lock_path = tmp_path / "qwen.lock"
        first = LinuxGuard(lock_path).acquire_lock()
        try:
            container = SimpleNamespace(linux=LinuxGuard(lock_path), core=object())
            with patch("modules.root_cli_main_entry._default_container", return_value=container):
                with pytest.raises(SingleInstanceError):
                    _run_cli_lifecycle(lambda _container: 0)
        finally:
            LinuxGuard(lock_path).release_lock(first)

    def test_mcp_container_is_lock_free(self) -> None:
        previous = root_mcp_main_entry._container
        fake_container = SimpleNamespace(core=object(), wire=MagicMock())
        try:
            root_mcp_main_entry._container = None
            with patch.object(root_mcp_main_entry, "SharedContainer", return_value=fake_container) as factory:
                root_mcp_main_entry._tools()
            factory.assert_called_once_with(use_linux_guard=False)
            fake_container.wire.assert_called_once_with()
        finally:
            root_mcp_main_entry._container = previous

    def test_main_reports_lock_failure(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        lock_path = tmp_path / "qwen.lock"
        first = LinuxGuard(lock_path).acquire_lock()
        try:
            container = SimpleNamespace(linux=LinuxGuard(lock_path), core=object())
            with patch("modules.root_cli_main_entry._default_container", return_value=container):
                result = main(["--login"])
            assert result == 1
            assert "already running" in capsys.readouterr().err
        finally:
            LinuxGuard(lock_path).release_lock(first)
