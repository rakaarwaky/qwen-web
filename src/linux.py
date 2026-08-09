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


class GracefulShutdown:
    """Context manager that installs SIGINT/SIGTERM handlers and sets a flag."""

    def __init__(self, root_dir: "Path | None" = None) -> None:
        self._root_dir = root_dir or Path("/tmp")
        self._shutdown_flag: threading.Event = threading.Event()
        self._original_sigint: Any = None
        self._original_sigterm: Any = None

    def __enter__(self) -> "GracefulShutdown":
        def _handler(_signum: int, _frame: Any) -> None:
            self._shutdown_flag.set()

        try:
            self._original_sigint = signal.signal(signal.SIGINT, _handler)
            self._original_sigterm = signal.signal(signal.SIGTERM, _handler)
        except (OSError, ValueError):
            pass
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        try:
            if self._original_sigint is not None:
                signal.signal(signal.SIGINT, self._original_sigint)
            if self._original_sigterm is not None:
                signal.signal(signal.SIGTERM, self._original_sigterm)
        except (OSError, ValueError):
            pass

    def __call__(self) -> bool:
        """Return True if shutdown has been requested."""
        return self._shutdown_flag.is_set()


def sd_notify(message: str, unset_environment: bool = False) -> None:
    """Send a message to systemd via the SD_LISTEN_PIDS / SD_NOTIFY socket."""
    pid_str = os.environ.get("SD_LISTEN_PIDS", "")
    if not pid_str:
        return

    try:
        if str(os.getpid()) not in pid_str:
            return
    except Exception:
        pass

    os.environ.setdefault("SD_NOTIFY", "1")
    os.environ["SD_NOTIFY"] = "1"

    if unset_environment:
        for key in ("SD_LISTEN_PIDS", "SD_LISTEN_FDS", "SD_LISTEN_NAMES"):
            os.environ.pop(key, None)


def sd_notify_ready() -> None:
    """Notify systemd that the application is ready."""
    sd_notify("READY=1")


def sd_notify_stop() -> None:
    """Notify systemd that the application is stopping gracefully."""
    sd_notify("STOPPING=1")
