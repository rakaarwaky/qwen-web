"""Centralized types, dataclasses, custom exceptions, and constants for qwen-cli.

Single source of truth — all modules import directly from here.
"""
from __future__ import annotations

import os
import time
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Callable, Optional

# ─── Constants: Paths & Defaults (XDG Specification) ──────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_xdg_dir(env_var: str, default_subpath: str) -> Path:
    env_val = os.getenv(env_var)
    if env_val:
        return Path(env_val) / "qwen-web"
    return Path.home() / default_subpath / "qwen-web"


XDG_DATA_HOME   = _get_xdg_dir("XDG_DATA_HOME", ".local/share")
XDG_STATE_HOME  = _get_xdg_dir("XDG_STATE_HOME", ".local/state")
XDG_CACHE_HOME  = _get_xdg_dir("XDG_STATE_HOME", ".cache")
XDG_CONFIG_HOME = _get_xdg_dir("XDG_CONFIG_HOME", ".config")

DEFAULT_TODO    = XDG_DATA_HOME / "input"
DEFAULT_PROC    = XDG_CACHE_HOME / ".processing"
DEFAULT_DONE    = XDG_DATA_HOME / "input" / "done"
DEFAULT_FAILED  = XDG_DATA_HOME / "input" / "failed"
DEFAULT_OUTPUT  = XDG_DATA_HOME / "output"
DEFAULT_LOG     = XDG_STATE_HOME / "log"
DEFAULT_SESSION = XDG_DATA_HOME / "qwen_session"
XDG_SKILL_MD    = XDG_DATA_HOME / "SKILL.md"
CHAT_URL        = "https://chat.qwen.ai/"

# ─── Constants: DOM Selectors ────────────────────────────────────────────────

NEW_CHAT_SELECTORS: tuple[str, ...] = (
    "[aria-label='New Chat']",
    "[aria-label*='New chat' i]",
    "button[aria-label*='New chat' i]",
    "div[aria-label*='New chat' i]",
)

INPUT_SELECTORS: tuple[str, ...] = (
    "textarea", "div[contenteditable='true']",
    "[placeholder*='Ask' i]", "[placeholder*='Message' i]",
    "#chat-input", ".chat-input",
)

SEND_SELECTORS: tuple[str, ...] = (
    "button[aria-label*='Send' i]:not([disabled])",
    "button[type='submit']:not([disabled])",
    "button[class*='send' i]:not([disabled])",
    "button[class*='submit' i]:not([disabled])",
    "button[id*='send' i]:not([disabled])",
    ".message-input-send-button:not([disabled])",
    "button:has(svg):not([disabled])",
)

MESSAGE_SELECTORS: tuple[str, ...] = (
    ".chat-message-assistant .markdown-body",
    "[class*='assistant'] .markdown-body",
    "[data-role='assistant']",
    ".qwen-markdown",
    ".markdown-body",
    "[class*='message-content']",
    "[class*='message-body']",
    "[class*='response']",
)

# ─── Constants: Pipeline Defaults ────────────────────────────────────────────

MAX_ATTEMPTS = 3
_WATCHER_SLEEP_CHUNK_SECS = 1

SERVICE_NAME = "qwen-web"

SD_NOTIFY_READY = "READY=1"
SD_NOTIFY_STOPPING = "STOPPING=1"
SD_NOTIFY_RELOADING = "RELOADING=1"

# ─── Exceptions ──────────────────────────────────────────────────────────────

class QwenCliError(RuntimeError):
    """Base exception for qwen-cli errors."""


class AuthRequiredError(QwenCliError):
    """Raised when authentication challenge/login is required in headless mode."""


class PromptInjectionError(QwenCliError):
    """Raised when prompt text injection into Qwen input fails across all strategies."""


class RateLimitError(QwenCliError):
    """Raised when the server returns a rate-limit / throttling response."""


class CircuitBreakerOpenError(QwenCliError):
    """Raised when the circuit breaker trips due to consecutive failures."""


class BrowserLaunchError(QwenCliError):
    """Raised when the browser context cannot be launched."""


class SingleInstanceError(RuntimeError):
    """Raised when another instance of qwen-cli is already running."""

# ─── Enums / Categorical Helpers ─────────────────────────────────────────────

class ErrorCategory:
    """Categorize errors for dashboards and alerting.

    Categories:
      - auth         : authentication / login / captcha issues
      - network      : connection lost, DNS, timeout
      - rate_limit   : server throttling (HTTP 429, etc.)
      - browser      : browser crash, launch failure, DOM error
      - injection    : prompt injection failed
      - parsing      : Qwen returned unexpected / empty response
      - file_io      : disk read/write errors
      - other        : uncategorized
    """

    @staticmethod
    def categorize(exc: BaseException) -> str:
        """Return the error category string."""
        exc_type = type(exc).__name__
        msg = str(exc).lower()

        if any(k in msg or k in exc_type.lower() for k in ("auth", "login", "captcha", "signin")):
            return "auth"
        if any(k in msg or k in exc_type.lower() for k in ("network", "connection", "timeout", "dns", "socket")):
            return "network"
        if any(k in msg or k in exc_type.lower() for k in ("rate", "limit", "throttl", "429")):
            return "rate_limit"
        if any(k in msg or k in exc_type.lower() for k in ("browser", "launch", "dom", "playwright", "chromium")):
            return "browser"
        if any(k in msg or k in exc_type.lower() for k in ("injection", "paste", "clipboard", "fill")):
            return "injection"
        if any(k in msg or k in exc_type.lower() for k in ("parse", "empty", "no response", "timeout")):
            return "parsing"
        if any(k in msg or k in exc_type.lower() for k in ("file", "io", "disk", "read", "write")):
            return "file_io"
        return "other"

# ─── Dataclasses (Entities) ─────────────────────────────────────────────────

@dataclass(frozen=True)
class AppConfig:
    """Application configuration with defaults and validation."""

    mode: str
    input_path: Path
    output_path: Path
    done_path: Path
    failed_path: Path
    proc_path: Path
    session_path: Path
    log_path: Path = DEFAULT_LOG

    interval: int = 3
    timeout: int = 300
    headless: bool = False
    prompt_file: Optional[Path] = None

    chrome_profile: str = "qwen-cli-profile"
    storage_state_file: Optional[Path] = None
    disable_sandbox: bool = True

    request_timeout: int = 120
    poll_interval: float = 1.0
    streaming_timeout: int = 180

    rate_limit_per_minute: int = 60
    circuit_breaker_threshold: int = 5
    circuit_breaker_window: int = 30

    retry_failed: bool = False

    @property
    def status_path(self) -> Path:
        """Path to the JSON status file for monitoring."""
        return self.log_path / "status.json"

    def validate(self) -> None:
        """Validate configuration before execution.

        Raises
        ------
        ValueError
            If any configuration value is invalid.
        """
        if self.timeout < 30:
            raise ValueError(f"timeout must be >= 30s, got {self.timeout}")
        if self.poll_interval < 0.5:
            raise ValueError(f"poll_interval must be >= 0.5s, got {self.poll_interval}")
        if self.request_timeout < 10:
            raise ValueError(f"request_timeout must be >= 10s, got {self.request_timeout}")
        if self.rate_limit_per_minute < 1:
            raise ValueError(f"rate_limit_per_minute must be >= 1, got {self.rate_limit_per_minute}")
        if self.circuit_breaker_threshold < 2:
            raise ValueError(f"circuit_breaker_threshold must be >= 2, got {self.circuit_breaker_threshold}")

    def __post_init__(self) -> None:
        """Validate config on construction."""
        self.validate()


@dataclass
class RunContext:
    """Run-scoped context with auto-generated run ID.

    Attributes
    ----------
    run_id : str
        Unique identifier: YYYYMMDD_HHMMSS_randomhex[:6].
    """

    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6])


# ─── Event System Types ──────────────────────────────────────────────────────

class QwenEventType(StrEnum):
    """Enterprise-level enum for Qwen Web pipeline event types (chronologically ordered)."""

    NETWORK_RECONNECTING  = "EVENT_NETWORK_RECONNECTING"  # Network reconnecting
    WEB_LOADED            = "EVENT_WEB_LOADED"            # Web page loaded
    DOCUMENT_PARSED       = "EVENT_DOCUMENT_PARSED"       # Document parsed
    SEND_CLICKED          = "EVENT_SEND_CLICKED"          # Send button clicked
    DISPATCH_ACKNOWLEDGED = "EVENT_DISPATCH_ACKNOWLEDGED" # Dispatch acknowledged
    THINKING_STARTED      = "EVENT_THINKING_STARTED"      # Qwen AI thinking
    STREAMING_GENERATION  = "EVENT_STREAMING_GENERATION"  # Qwen AI typing (realtime)
    GENERATION_FINISHED   = "EVENT_GENERATION_FINISHED"   # Generation finished
    OUTPUT_COPIED         = "EVENT_OUTPUT_COPIED"         # Output saved


EVENT_NETWORK_RECONNECTING = QwenEventType.NETWORK_RECONNECTING
EVENT_WEB_LOADED           = QwenEventType.WEB_LOADED
EVENT_DOCUMENT_PARSED      = QwenEventType.DOCUMENT_PARSED
EVENT_SEND_CLICKED         = QwenEventType.SEND_CLICKED
EVENT_DISPATCH_ACKNOWLEDGED= QwenEventType.DISPATCH_ACKNOWLEDGED
EVENT_THINKING_STARTED     = QwenEventType.THINKING_STARTED
EVENT_STREAMING_GENERATION = QwenEventType.STREAMING_GENERATION
EVENT_GENERATION_FINISHED  = QwenEventType.GENERATION_FINISHED
EVENT_OUTPUT_COPIED        = QwenEventType.OUTPUT_COPIED


@dataclass
class LifecycleEvent:
    """Structured event emitted at every major lifecycle boundary."""

    name: str
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    details: dict = field(default_factory=dict)


LifecycleCallback = Callable[[LifecycleEvent], None]


EVENT_DESCRIPTIONS: dict[str, str] = {
    "EVENT_NETWORK_RECONNECTING": "Reconnecting to Qwen Web...",
    "EVENT_WEB_LOADED": "Qwen Web page loaded",
    "EVENT_DOCUMENT_PARSED": "Document parsed",
    "EVENT_SEND_CLICKED": "Send button clicked",
    "EVENT_DISPATCH_ACKNOWLEDGED": "Dispatch acknowledged",
    "EVENT_THINKING_STARTED": "Qwen AI thinking...",
    "EVENT_STREAMING_GENERATION": "Qwen AI typing...",
    "EVENT_GENERATION_FINISHED": "Generation finished",
    "EVENT_OUTPUT_COPIED": "Output saved",
}


class LifecycleEmitter:
    """Simple event bus for pipeline lifecycle events with typed dispatcher capability."""

    def __init__(self) -> None:
        self._callbacks: dict[str, list[LifecycleCallback]] = {}

    def on(self, event_name: QwenEventType | str, callback: LifecycleCallback) -> None:
        """Register a callback for a named lifecycle event."""
        key = str(event_name)
        self._callbacks.setdefault(key, []).append(callback)

    def emit(self, event_name: QwenEventType | str, details: Optional[dict] = None) -> LifecycleEvent:
        """Emit a lifecycle event to all registered callbacks."""
        key = str(event_name)
        evt = LifecycleEvent(
            name=key,
            timestamp=time.time(),
            details=details or {},
        )
        logger = logging.getLogger("qwen-cli")
        label = EVENT_DESCRIPTIONS.get(key, key)
        detail_str = f" - {details}" if details else ""
        logger.info(f"[{key}] {label}{detail_str}")
        for cb in self._callbacks.get(key, []):
            try:
                cb(evt)
            except Exception as exc:
                logger.warning(f"lifecycle_callback_error event={key} error={str(exc)}")
        return evt


# ─── Metrics counter (P8) ────────────────────────────────────────────────────

class MetricsCounter:
    """Simple in-memory metrics collector for request/file stats.

    Thread-safe via threading.Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._start_time = datetime.now()

    def increment(self, key: str, amount: int = 1) -> None:
        """Increment a counter by amount."""
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + amount

    def get(self, key: str) -> int:
        """Get current counter value."""
        with self._lock:
            return self._counters.get(key, 0)

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of all counters."""
        with self._lock:
            return dict(self._counters)


# ─── Status file writer (P8) ────────────────────────────────────────────────

class StatusFileWriter:
    """Writes a JSON status file that systemd / monitoring tools can read.

    The status file is updated on every major lifecycle event.
    """

    def __init__(self, status_path: Path) -> None:
        self._status_path = status_path
        self._status_path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        status: str,
        mode: str,
        headless: bool,
        run_id: Optional[str] = None,
        error: Optional[str] = None,
        cpu_sec: Optional[float] = None,
        files_processed: int = 0,
        files_failed: int = 0,
    ) -> None:
        """Atomically write the current status to disk."""
        rec: dict[str, Any] = {
            "status": status,
            "mode": mode,
            "headless": headless,
            "run_id": run_id,
            "files_processed": files_processed,
            "files_failed": files_failed,
        }
        if cpu_sec is not None:
            rec["cpu_sec"] = round(cpu_sec, 2)
        if error:
            rec["error"] = error

        tmp_path = self._status_path.with_suffix(".tmp")
        try:
            import json
            tmp_path.write_text(
                json.dumps(rec, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            tmp_path.rename(self._status_path)
        except Exception:
            pass

    def read(self) -> Optional[dict[str, Any]]:
        """Read the last written status file."""
        try:
            import json
            return json.loads(self._status_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        except FileNotFoundError:
            return None
        except Exception:
            return None

# ─── Circuit Breaker Entity ──────────────────────────────────────────────────

class CircuitBreaker:
    """Sliding-window circuit breaker for request-level failure tracking."""

    def __init__(self, threshold: int = 5, window_sec: int = 30) -> None:
        self._threshold = threshold
        self._window_sec = window_sec
        self._failures: list[float] = []
        self._trip: bool = False

    def record_success(self) -> None:
        """Reset the breaker on a successful request."""
        self._failures.clear()
        self._trip = False

    def record_failure(self) -> None:
        """Record a failure and trip if threshold exceeded within window."""
        now = time.time()
        self._failures.append(now)
        while self._failures and (now - self._failures[0]) > self._window_sec:
            self._failures.pop(0)
        if len(self._failures) >= self._threshold:
            self._trip = True

    @property
    def is_tripped(self) -> bool:
        """True when the breaker has tripped."""
        return self._trip


# ─── Rate Limiter Entity ─────────────────────────────────────────────────────

class RateLimiter:
    """Simple token-bucket rate limiter for request throttling."""

    def __init__(self, max_per_minute: int = 60) -> None:
        self._max_per_minute = max_per_minute
        self._timestamps: list[float] = []

    def acquire(self) -> None:
        """Wait until a request slot is available."""
        now = time.time()
        window_start = now - 60.0
        while True:
            while self._timestamps and self._timestamps[0] < window_start:
                self._timestamps.pop(0)
            if len(self._timestamps) < self._max_per_minute:
                break
            oldest = self._timestamps[0]
            wait_sec = 60.0 - (now - oldest) + 0.1
            if wait_sec > 0:
                time.sleep(wait_sec)
                now = time.time()
        self._timestamps.append(time.time())

# ─── Single-Instance Lock Entity ─────────────────────────────────────────────

class SingleInstanceLock:
    """File-based single-instance lock using fcntl.flock()."""

    def __init__(self, lock_path: Optional[Path] = None) -> None:
        import tempfile
        self._lock_path = (
            lock_path or Path(tempfile.gettempdir()) / "qwen-cli.lock"
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

# ─── Graceful Shutdown Entity ────────────────────────────────────────────────

class GracefulShutdown:
    """Context manager that installs SIGINT/SIGTERM handlers and sets a flag."""

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


# ─── sd_notify Functions ─────────────────────────────────────────────────────

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
    sd_notify(SD_NOTIFY_READY)


def sd_notify_stop() -> None:
    """Notify systemd that the application is stopping gracefully."""
    sd_notify(SD_NOTIFY_STOPPING)


