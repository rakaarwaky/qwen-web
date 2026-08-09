"""Configuration constants, DOM selectors, dataclasses, and custom exceptions for qwen-cli."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── Custom Exceptions ───────────────────────────────────────────────────────
class AuthRequiredError(RuntimeError):
    """Raised when authentication challenge/login is required in headless mode."""
    pass


class PromptInjectionError(RuntimeError):
    """Raised when prompt text injection into Qwen input fails across all strategies."""
    pass


# ─── Paths & Defaults ────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).resolve().parent.parent
DEFAULT_TODO    = BASE_DIR / "input"
DEFAULT_PROC    = BASE_DIR / "input" / ".processing"
DEFAULT_DONE    = BASE_DIR / "input" / "done"
DEFAULT_FAILED  = BASE_DIR / "input" / "failed"
DEFAULT_OUTPUT  = BASE_DIR / "output"
DEFAULT_LOG     = BASE_DIR / "log"
DEFAULT_SESSION = BASE_DIR / "qwen_session"
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


@dataclass
class RunContext:
    run_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6])
