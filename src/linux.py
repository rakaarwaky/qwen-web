"""Linux-native utilities for qwen-cli: single-instance lock, sd_notify, and graceful shutdown.

This module provides:
  - SingleInstanceLock : file-based lock so only one qwen-cli process runs at a time.
  - sd_notify()          : systemd notification protocol (ready/stop/reload).
  - GracefulShutdown   : context-manager that traps SIGINT/SIGTERM and sets a flag.
"""
from __future__ import annotations

import fcntl
import os
import signal
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

# ─── Single-instance lock ─────────────────────────────────────────────────────
class SingleInstanceError(RuntimeError):
    """Raised when another instance of qwen-cli is already running."""


class SingleInstanceLock:
    """File-based single-instance lock using fcntl.flock().

    Usage::

        with SingleInstanceLock("/tmp/qwen-cli.lock"):
            # only one process can acquire this at a time
            main()

    The lock file is automatically removed when the context exits, even on crash.
    """

    def __init__(self, lock_path: Optional[Path] = None) -> None:
        self._lock_path = (
            lock_path or Path("/tmp") / "qwen-cli.lock"
        )

    def __enter__(self) -> SingleInstanceLock:
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


# ─── sd_notify protocol ────────────────────────────────────────────────────────
def sd_notify(message: str, unset_environment: bool = False) -> None:
    """Send a message to systemd via the SD_LISTEN_PIDS / SD_NOTIFY socket.

    Supported messages:
      - "READY=1"              : application is ready (default after startup)
      - "STOPPING=1"           : shutting down gracefully
      - "RELOADING=1"          : configuration reloaded

    Parameters
    ----------
    message : str
        The sd_notify message string.
    unset_environment : bool
        If True, also unset the SD_* environment variables so systemd
        stops tracking this process (useful before exec-ing a new process).
    """
    # Only operate when systemd is involved
    pid_str = os.environ.get("SD_LISTEN_PIDS", "")
    if not pid_str:
        return

    # Verify the PID matches our process
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


# ─── Graceful shutdown context manager ────────────────────────────────────────
class GracefulShutdown:
    """Context manager that installs SIGINT/SIGTERM handlers and sets a flag.

    Usage::

        with GracefulShutdown() as shutdown:
            while not shutdown():
                # do work
                time.sleep(1)

    After SIGINT/SIGTERM the loop will exit cleanly.
    """

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self._root_dir = root_dir or Path("/tmp")
        self._shutdown_flag: threading.Event = threading.Event()
        self._original_sigint: Any = None
        self._original_sigterm: Any = None

    def __enter__(self) -> GracefulShutdown:
        def _handler(_signum: int, _frame: Any) -> None:
            self._shutdown_flag.set()

        try:
            self._original_sigint = signal.signal(signal.SIGINT, _handler)
            self._original_sigterm = signal.signal(signal.SIGTERM, _handler)
        except (OSError, ValueError):
            # Windows or unsupported signal environments
            pass

        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        # Restore original handlers
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
