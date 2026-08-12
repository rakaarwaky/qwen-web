"""Core domain constants: DOM selectors, auth/challenge keywords.

Taxonomy layer (taxonomy(constant)): pure literals only.
"""

from __future__ import annotations

from modules.shared.src.common.taxonomy_core_constant import CHAT_URL

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
    ".chat-message-assistant .markdown-body",
    "[class*='assistant'] .markdown-body",
    "[class*='assistant'] [class*='markdown']",
    "[data-role='assistant']",
    ".qwen-markdown",
    ".chat-message-assistant",
    "div.assistant",
    ".assistant",
)

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

CHAT_URL_CONST = CHAT_URL
