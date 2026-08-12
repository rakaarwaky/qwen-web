"""Capabilities: Linux-native guards (AES403).

Implements ILinuxProtocol — single-instance file lock (fcntl) and systemd
sd_notify socket notifications.
"""

from __future__ import annotations

import contextlib
import fcntl
import os
import socket
import tempfile
import types
from pathlib import Path
from typing import Any

from modules.shared.src.contract_core_protocol import ILinuxProtocol
from modules.shared.src.taxonomy_domain_error import SingleInstanceError

# Block 1: Class Definition & Constructor
class SingleInstanceLock:
    """File-based single-instance lock using fcntl.flock()."""

    def __init__(self, lock_path: Path | None = None) -> None:
        """Initialize with an optional custom lock file path."""
        self._lock_path = lock_path or Path(tempfile.gettempdir()) / "qwen-cli.lock"
        self._lock_fd: Any = None

    def __enter__(self) -> SingleInstanceLock:
        """Acquire the file lock; raise SingleInstanceError if already held."""
        self._lock_fd = open(self._lock_path, "w")
        try:
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as err:
            self._lock_fd.close()
            raise SingleInstanceError(
                "Another instance of qwen-cli is already running. "
                f"Lock file: {self._lock_path}"
            ) from err
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        """Release the file lock and clean up the lock file."""
        try:
            with contextlib.suppress(Exception):
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                self._lock_fd.close()
        finally:
            with contextlib.suppress(Exception):
                self._lock_path.unlink(missing_ok=True)
class LinuxGuard(ILinuxProtocol):
    """Linux-native guard: single-instance lock and sd_notify notifications."""

    def __init__(self, lock_path: Path | None = None) -> None:
        """Initialize with an optional custom lock file path."""
        self._lock_path = lock_path

# Block 2: Public Contract


    def acquire_lock(self) -> SingleInstanceLock:
        """Acquire the single-instance file lock."""
        return SingleInstanceLock(self._lock_path).__enter__()

    # ─── Block 2: Public Contract (ILinuxProtocol ONLY) ──
    def release_lock(self, lock: Any) -> None:
        """Release a previously acquired lock."""
        if isinstance(lock, SingleInstanceLock):
            lock.__exit__(None, None, None)

    def sd_notify_ready(self) -> None:
        """Notify systemd that the application is ready."""
        self._sd_notify("READY=1")

    def sd_notify_stop(self) -> None:
        """Notify systemd that the application is stopping gracefully."""
        self._sd_notify("STOPPING=1")

# Block 3: Dunder Methods, Factories & Helpers


    def _sd_notify(self, message: str, unset_environment: bool = False) -> None:
        """Send a message to systemd via the NOTIFY_SOCKET Unix datagram socket."""
        notify_socket = os.environ.get("NOTIFY_SOCKET")
        if not notify_socket:
            return

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            if notify_socket[0] == "@":
                notify_socket = "\0" + notify_socket[1:]
            sock.connect(notify_socket)
            sock.sendall(message.encode("utf-8"))
            sock.close()
        except (OSError, ConnectionError):
            pass

        if unset_environment:
            for key in ("NOTIFY_SOCKET", "WATCHDOG_USEC", "WATCHDOG_PID"):
                os.environ.pop(key, None)

    def __repr__(self) -> str:
        """Return string representation of LinuxGuard."""
        return f"LinuxGuard(lock_path={self._lock_path!r})"


# ─── Module-level convenience functions ──────────────────────────────────────
def sd_notify(message: str, unset_environment: bool = False) -> None:
    """Send a raw message to systemd (module-level convenience)."""
    LinuxGuard()._sd_notify(message, unset_environment)


def sd_notify_ready() -> None:
    """Notify systemd that the application is ready (module-level convenience)."""
    LinuxGuard().sd_notify_ready()


def sd_notify_stop() -> None:
    """Notify systemd that the application is stopping (module-level convenience)."""
    LinuxGuard().sd_notify_stop()
