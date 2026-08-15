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

# ─── Role path skip sets ──────────────────────────────────────
SKIP_DIRS: frozenset[str] = frozenset(
    {
        "done",
        "failed",
        ".processing",
        "proc",
    }
)

ROLE_PATH_SKIP_DIRS: frozenset[str] = frozenset(
    {
        "todo",
        "done",
        "failed",
        ".processing",
        "proc",
    }
)

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

DEFAULT_TODO = XDG_DATA_HOME / "input"
DEFAULT_PROC = XDG_CACHE_HOME / ".processing"
DEFAULT_DONE = XDG_DATA_HOME / "input" / "done"
DEFAULT_FAILED = XDG_DATA_HOME / "input" / "failed"
DEFAULT_OUTPUT = XDG_DATA_HOME / "output"
DEFAULT_LOG = XDG_STATE_HOME / "log"
DEFAULT_SESSION = XDG_DATA_HOME / "qwen_session"
XDG_SKILL_MD = XDG_DATA_HOME / "SKILL.md"
CHAT_URL = "https://chat.qwen.ai/"

MAX_ATTEMPTS = 3
_WATCHER_SLEEP_CHUNK_SECS = 1

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
    "textarea",
    "div[contenteditable='true']",
    "[placeholder*='Ask' i]",
    "[placeholder*='Message' i]",
    "#chat-input",
    ".chat-input",
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
    ".chat-response-message .response-message-content",
    ".chat-response-message .qwen-markdown-text",
    ".chat-response-message .qwen-markdown",
    ".chat-message-assistant .markdown-body",
    "[class*='assistant'] .markdown-body",
    "[class*='assistant'] [class*='markdown']",
    "[data-role='assistant']",
    ".qwen-markdown",
    ".chat-message-assistant",
    ".qwen-chat-message-assistant",
    ".chat-response-message",
    ".chat-messages-container",
    "div.assistant",
    ".assistant",
)

COMBINED_MESSAGE_SELECTOR: str = ", ".join(MESSAGE_SELECTORS)
RESPONSE_CONTENT_SELECTOR: str = ".response-message-content, .qwen-markdown-text"

STOP_BUTTON_SELECTORS: str = (
    "button[aria-label*='Stop' i], button:has-text('Stop'), [class*='stop-btn'], [class*='icon-stop']"
)
SEND_DISABLED_SELECTORS: str = "button[aria-label*='Send' i][disabled], button[class*='send' i][disabled]"
TYPING_INDICATOR_SELECTORS: str = (
    ".thinking:not([style*='display: none']):not([class*='completed']), "
    "[class*='qwen-chat-thinking-status-card']:not([class*='completed']), "
    "[class*='typing'], [class*='streaming']"
)

JS_GET_RESPONSE_TEXT: str = """
() => {
    var responseNodes = document.querySelectorAll(
        '.response-message-content, .qwen-markdown-text, ' +
        '.chat-response-message .qwen-markdown, .qwen-chat-message-assistant .qwen-markdown'
    );
    for (var ri = responseNodes.length - 1; ri >= 0; ri--) {
        var responseNode = responseNodes[ri];
        if (responseNode.closest('.qwen-chat-message-user')) continue;
        var responseText = (responseNode.innerText || '').trim();
        if (responseText.length > 0) return responseText;
    }
    var SKIP_CLASSES = [
        'model-selector', 'fileitem', 'placeholder', 'message-input',
        'header', 'footer', 'feedback', 'downLoad', 'sidebar',
        'mode-select', 'send-button', 'toolbar', 'nav', 'spinner',
        'thinking', 'attachment', 'file-card', 'file-content',
        'chat-footer', 'chat-prompt-recommend'
    ];
    function isInChrome(el) {
        var p = el;
        while (p) {
            var cls = p.className;
            if (cls && typeof cls === 'string') {
                for (var i = 0; i < SKIP_CLASSES.length; i++) {
                    if (cls.indexOf(SKIP_CLASSES[i]) >= 0) return true;
                }
            }
            if (p.tagName === 'HEADER' || p.tagName === 'FOOTER' ||
                p.tagName === 'NAV' || p.tagName === 'ASIDE') return true;
            p = p.parentElement;
        }
        return false;
    }
    var assistantNodes = document.querySelectorAll(
        '.qwen-chat-message-assistant, .chat-message-assistant, [data-role="assistant"]'
    );
    for (var ai = assistantNodes.length - 1; ai >= 0; ai--) {
        var assistantText = (assistantNodes[ai].innerText || '').trim();
        if (assistantText.length > 0 && !isInChrome(assistantNodes[ai])) return assistantText;
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

AUTH_KEYWORDS = ("login", "passport", "auth", "signin", "account", "sso")

LOGIN_FORM_SELECTORS: tuple[str, ...] = (
    "input[type='password']",
    "input[name='password']",
    "button:has-text('Log in')",
    "button:has-text('Sign in')",
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
