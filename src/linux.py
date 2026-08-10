"""Linux-native utilities for qwen-cli: single-instance lock, sd_notify, and graceful shutdown.

All types are centralized in src/types.py — import directly from there.
"""
from __future__ import annotations

import fcntl
import os
import signal
import tempfile
import threading
from pathlib import Path
from typing import Any

from .types import SingleInstanceError


class SingleInstanceLock:
    """File-based single-instance lock using fcntl.flock()."""

    def __init__(self, lock_path: "Path | None" = None) -> None:
        self._lock_path = (
            lock_path or Path(tempfile.gettempdir()) / "qwen-cli.lock"
        )

    def __enter__(self) -> "SingleInstanceLock":
        self._lock_fd = open(self._lock_path, "w")
        try:
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock_fd.close()
            raise SingleInstanceError(
                "Another instance of qwen-cli is already running. "
                f"Lock file: {self._lock_path}"
            )
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        try:
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
            self._lock_fd.close()
        except Exception:
            pass
        finally:
            try:
                self._lock_path.unlink(missing_ok=True)
            except Exception:
                pass



def sd_notify(message: str, unset_environment: bool = False) -> None:
    """Send a message to systemd via the NOTIFY_SOCKET Unix datagram socket.

    This is the real sd_notify protocol — NOT an environment variable hack.
    systemd expects a UDP datagram sent to the Unix socket at $NOTIFY_SOCKET.
    """
    notify_socket = os.environ.get("NOTIFY_SOCKET")
    if not notify_socket:
        return

    import socket
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        if notify_socket[0] == "@":
            notify_socket = "\0" + notify_socket[1:]
        sock.connect(notify_socket)
        sock.sendall(message.encode("utf-8"))
        sock.close()
    except Exception:
        pass

    if unset_environment:
        for key in ("NOTIFY_SOCKET", "WATCHDOG_USEC", "WATCHDOG_PID"):
            os.environ.pop(key, None)


def sd_notify_ready() -> None:
    """Notify systemd that the application is ready."""
    sd_notify("READY=1")


def sd_notify_stop() -> None:
    """Notify systemd that the application is stopping gracefully."""
    sd_notify("STOPPING=1")
