"""Core domain + cross-cutting constants for qwen-web: XDG paths, chat URL,
service name, DOM selectors, and auth/challenge keywords.

Taxonomy layer (taxonomy(constant)): pure literals and constant values only.
"""

from __future__ import annotations

import os
from pathlib import Path

from modules.shared.src.taxonomy_core_vo import (
    AtomicWriteFlag,
    GenerateSidecarFlag,
    IncludeHeaderFlag,
)

BASE_DIR = Path(__file__).resolve().parents[3]

STATUS_FILENAME: str = "status.json"

# ─── Application paths ────────────────────────────────────────

XDG_DATA_HOME = (
    Path(os.environ["XDG_DATA_HOME"]) / "qwen-web"
    if os.environ.get("XDG_DATA_HOME")
    else Path.home() / ".local/share/qwen-web"
)
XDG_STATE_HOME = (
    Path(os.environ["XDG_STATE_HOME"]) / "qwen-web"
    if os.environ.get("XDG_STATE_HOME")
    else Path.home() / ".local/state/qwen-web"
)
XDG_CACHE_HOME = (
    Path(os.environ["XDG_CACHE_HOME"]) / "qwen-web"
    if os.environ.get("XDG_CACHE_HOME")
    else Path.home() / ".cache/qwen-web"
)
XDG_CONFIG_HOME = (
    Path(os.environ["XDG_CONFIG_HOME"]) / "qwen-web"
    if os.environ.get("XDG_CONFIG_HOME")
    else Path.home() / ".config/qwen-web"
)

DEFAULT_OUTPUT = XDG_DATA_HOME / "output"
DEFAULT_LOG = XDG_STATE_HOME / "log"
DEFAULT_SESSION = XDG_DATA_HOME / "qwen_session"
DEFAULT_TODO = XDG_DATA_HOME / "todo"
XDG_SKILL_MD = XDG_DATA_HOME / "SKILL.md"
CHAT_URL = "https://chat.qwen.ai/"

MAX_ATTEMPTS = 3

SERVICE_NAME = "qwen-web"

SD_NOTIFY_READY = "READY=1"
SD_NOTIFY_STOPPING = "STOPPING=1"
SD_NOTIFY_RELOADING = "RELOADING=1"

TEXTAREA_SELECTOR = "textarea.message-input-textarea"

NEW_CHAT_SELECTORS: tuple[str, ...] = (
    "[aria-label='New Chat']",
    "[aria-label*='New chat' i]",
    "button[aria-label*='New chat' i]",
    "div[aria-label*='New chat' i]",
)

INPUT_SELECTORS: tuple[str, ...] = (
    "textarea.message-input-textarea",
    "textarea",
    "[placeholder*='Ask' i]",
    "[placeholder*='Message' i]",
)

SEND_SELECTORS: tuple[str, ...] = (
    ".message-input-right-button-send button",
    "button[aria-label*='Send' i]:not(.disabled):not([disabled])",
    "button[type='submit']:not(.disabled):not([disabled])",
    "button[class*='send' i]:not(.disabled):not([disabled])",
)

MESSAGE_SELECTORS: tuple[str, ...] = (
    ".qwen-chat-message-assistant",
    ".chat-response-message",
    ".qwen-markdown",
    ".markdown-body",
    "[class*='assistant'] [class*='markdown']",
)

COMBINED_MESSAGE_SELECTOR: str = ", ".join(MESSAGE_SELECTORS)
RESPONSE_CONTENT_SELECTOR: str = ".qwen-markdown, .markdown-body, .response-message-content, .qwen-markdown-text"

STOP_BUTTON_SELECTORS: str = (
    "button[aria-label*='Stop' i], button:has-text('Stop'), [class*='stop-btn'], [class*='icon-stop']"
)
SEND_DISABLED_SELECTORS: str = "button[aria-label*='Send' i][disabled], button[class*='send' i][disabled]"
TYPING_INDICATOR_SELECTORS: str = (
    ".thinking:not([style*='display: none']):not([class*='completed']), "
    "[class*='qwen-chat-thinking-status-card']:not([class*='completed']), "
    "[class*='typing'], [class*='streaming']"
)

JS_GET_RESPONSE_TEXT: str = r"""
() => {
    var responseNodes = document.querySelectorAll(
        '.qwen-markdown, .chat-response-message, .response-message-content, .qwen-markdown-text'
    );
    for (var ri = responseNodes.length - 1; ri >= 0; ri--) {
        var responseNode = responseNodes[ri];
        if (responseNode.closest('.qwen-chat-message-user') || responseNode.closest('.user-message-content')) continue;
        var outerContainer = responseNode.closest('.qwen-markdown, .chat-response-message');
        var targetNode = outerContainer || responseNode;
        var responseText = (targetNode.innerText || '').trim();
        if (responseText.startsWith("Thinking completed")) {
            responseText = responseText.replace(/^Thinking completed\s*/, '');
        }
        if (responseText.length > 0) return responseText;
    }
    return null;
}
"""

JS_COUNT_TURNS: str = """
() => {
    var turns = document.querySelectorAll(
        '.chat-response-message, [class*="chat-message"], [class*="message-item"], '
        + '[class*="virtual-list-item"], [class*="turn"]'
    );
    return turns.length;
}
"""

AUTH_KEYWORDS = ("login", "passport", "auth", "signin", "account", "sso", "guest")

LOGIN_FORM_SELECTORS: tuple[str, ...] = (
    "input[type='password']",
    "input[name='password']",
    "button:has-text('Log in')",
    "a:has-text('Log in')",
    "button:has-text('Sign in')",
    "a:has-text('Sign in')",
    "button:has-text('Sign up')",
    "a:has-text('Sign up')",
    ".login-form",
    "[class*='login']",
    "[class*='passport']",
)

CHALLENGE_KEYWORDS: tuple[str, ...] = (
    "just a moment",
    "attention required!",
    "verify you are human",
    "enable javascript and cookies",
    "502 bad gateway",
    "504 gateway time-out",
    "service unavailable",
    "access denied",
    "oops! there are files still uploading",
    "files still uploading",
    "please wait for the upload to complete",
    "please wait until the uploaded",
    "currently parsing file",
    "finished processing before sending",
    "failed to upload",
    "something went wrong",
)

# ─── Saver defaults ─────────────────────────────────────────
DEFAULT_INCLUDE_HEADER = IncludeHeaderFlag(True)
DEFAULT_GENERATE_SIDECAR = GenerateSidecarFlag(True)
DEFAULT_ATOMIC_WRITE = AtomicWriteFlag(True)
