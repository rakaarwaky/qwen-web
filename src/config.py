"""Configuration constants, DOM selectors, dataclasses, and custom exceptions for qwen-cli."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

# ─── Custom Exceptions ───────────────────────────────────────────────────────
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


# ─── Paths & Defaults (XDG Specification) ──────────────────────────────────────
import os

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

# ─── DOM Selectors ───────────────────────────────────────────────────────────
NEW_CHAT_SELECTORS = (
    "[aria-label='New Chat']",
    "[aria-label*='New chat' i]",
    "button[aria-label*='New chat' i]",
    "div[aria-label*='New chat' i]",
)
INPUT_SELECTORS = (
    "textarea", "div[contenteditable='true']",
    "[placeholder*='Ask' i]", "[placeholder*='Message' i]",
    "#chat-input", ".chat-input",
)
SEND_SELECTORS = (
    "button[aria-label*='Send' i]:not([disabled])",
    "button[type='submit']:not([disabled])",
    "button[class*='send' i]:not([disabled])",
    "button[class*='submit' i]:not([disabled])",
    "button[id*='send' i]:not([disabled])",
    ".message-input-send-button:not([disabled])",
    "button:has(svg):not([disabled])",
)
MESSAGE_SELECTORS = (
    ".chat-message-assistant .markdown-body",
    "[class*='assistant'] .markdown-body",
    "[data-role='assistant']",
    ".qwen-markdown",
    ".markdown-body",
    "[class*='message-content']",
    "[class*='message-body']",
    "[class*='response']",
)


# ─── Config dataclasses ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class AppConfig:
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

    # ── Browser profile (P5) ────────────────────────────────────────────────
    chrome_profile: str = "qwen-cli-profile"  # Chrome user-data-dir name
    storage_state_file: Optional[Path] = None  # path to storage-state JSON
    disable_sandbox: bool = True                 # --no-sandbox for Linux

    # ── Request / polling timeouts (P2) ────────────────────────────────────
    request_timeout: int = 120      # seconds to wait for Qwen to respond
    poll_interval: float = 1.0      # seconds between message-poll checks
    streaming_timeout: int = 180   # max time to wait for streaming generation

    # ── Rate limiting (P2) ────────────────────────────────────────────────
    rate_limit_per_minute: int = 60  # max requests per minute

    # ── Circuit breaker (P2) ──────────────────────────────────────────────
    circuit_breaker_threshold: int = 5   # consecutive failures to trip
    circuit_breaker_window: int = 30     # seconds sliding window

    # ── Retry-failed mode (P6) ────────────────────────────────────────────
    retry_failed: bool = False           # process files in failed/ on next run

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
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6])
