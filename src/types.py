"""Centralized types, dataclasses, custom exceptions, and constants for qwen-cli.

Single source of truth — all modules import directly from here.
"""
from __future__ import annotations

import os
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable

# ─── Constants: Paths & Defaults (XDG Specification) ──────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_xdg_dir(env_var: str, default_subpath: str) -> Path:
    env_val = os.getenv(env_var)
    if env_val:
        return Path(env_val) / "qwen-web"
    return Path.home() / default_subpath / "qwen-web"


XDG_DATA_HOME   = _get_xdg_dir("XDG_DATA_HOME", ".local/share")
XDG_STATE_HOME  = _get_xdg_dir("XDG_STATE_HOME", ".local/state")
XDG_CACHE_HOME  = _get_xdg_dir("XDG_CACHE_HOME", ".cache")
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


class ElementNotFoundError(QwenCliError):
    """Raised when a required DOM element is not found on the page."""


class NetworkTimeoutError(QwenCliError):
    """Raised when network operation times out or drops."""


class OutputValidationError(QwenCliError):
    """Raised when response content fails sanity check (e.g. captcha/error page)."""

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
    prompt_file: Path | None = None

    chrome_profile: str = "qwen-cli-profile"
    storage_state_file: Path | None = None
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
    details: dict[str, Any] = field(default_factory=dict)


LifecycleCallback = Callable[[LifecycleEvent], None]


EVENT_DESCRIPTIONS: dict[QwenEventType, str] = {
    QwenEventType.NETWORK_RECONNECTING: "Reconnecting to Qwen Web...",
    QwenEventType.WEB_LOADED: "Qwen Web page loaded",
    QwenEventType.DOCUMENT_PARSED: "Document parsed",
    QwenEventType.SEND_CLICKED: "Send button clicked",
    QwenEventType.DISPATCH_ACKNOWLEDGED: "Dispatch acknowledged",
    QwenEventType.THINKING_STARTED: "Qwen AI thinking...",
    QwenEventType.STREAMING_GENERATION: "Qwen AI typing...",
    QwenEventType.GENERATION_FINISHED: "Generation finished",
    QwenEventType.OUTPUT_COPIED: "Output saved",
}


class LifecycleEmitter:
    """Simple event bus for pipeline lifecycle events with typed dispatcher capability."""

    def __init__(self) -> None:
        self._callbacks: dict[str, list[LifecycleCallback]] = {}

    def on(self, event_name: QwenEventType | str, callback: LifecycleCallback) -> None:
        """Register a callback for a named lifecycle event."""
        key = str(event_name)
        self._callbacks.setdefault(key, []).append(callback)

    def emit(self, event_name: QwenEventType | str, details: dict[str, Any] | None = None) -> LifecycleEvent:
        """Emit a lifecycle event to all registered callbacks."""
        key = str(event_name)
        evt = LifecycleEvent(
            name=key,
            timestamp=time.time(),
            details=details or {},
        )
        from .observability import get_logger
        logger = get_logger()
        enum_member = event_name if isinstance(event_name, QwenEventType) else None
        label = EVENT_DESCRIPTIONS.get(enum_member, key) if enum_member else key
        detail_str = f" - {details}" if details else ""
        logger.info(f"[{key}] {label}{detail_str}")
        for cb in self._callbacks.get(key, []):
            try:
                cb(evt)
            except Exception as exc:
                logger.warning(f"lifecycle_callback_error event={key} error={exc}")
        return evt



# ─── Circuit Breaker Entity ──────────────────────────────────────────────────

class CircuitBreaker:
    """Sliding-window circuit breaker for request-level failure tracking."""

    def __init__(self, threshold: int = 5, window_sec: int = 30) -> None:
        if threshold < 1:
            raise ValueError(f"threshold must be >= 1, got {threshold}")
        if window_sec < 1:
            raise ValueError(f"window_sec must be >= 1, got {window_sec}")
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
            self._failures.popleft()
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
        if max_per_minute < 1:
            raise ValueError(f"max_per_minute must be >= 1, got {max_per_minute}")
        self._max_per_minute = max_per_minute
        self._timestamps: deque[float] = deque()

    def acquire(self) -> None:
        """Wait until a request slot is available."""
        now = time.time()
        window_start = now - 60.0
        while True:
            while self._timestamps and self._timestamps[0] < window_start:
                self._timestamps.popleft()
            if len(self._timestamps) < self._max_per_minute:
                break
            oldest = self._timestamps[0]
            wait_sec = max(0.1, 60.0 - (now - oldest) + 0.1)
            time.sleep(wait_sec)
            now = time.time()
            window_start = now - 60.0
        self._timestamps.append(time.time())



