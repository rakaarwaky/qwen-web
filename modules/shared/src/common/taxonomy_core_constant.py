"""Core cross-cutting constants for qwen-web: XDG paths, chat URL, service name.

Taxonomy layer (taxonomy(constant)): pure literals and path resolution only.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[4]


def _get_xdg_dir(env_var: str, default_subpath: str) -> Path:
    """Resolve an XDG Base Directory Specification path.

    Checks the environment variable first; falls back to ~/default_subpath.
    Appends 'qwen-web' as the application subdirectory.
    """
    env_val = os.getenv(env_var)
    if env_val:
        return Path(env_val) / "qwen-web"
    return Path.home() / default_subpath / "qwen-web"


XDG_DATA_HOME = _get_xdg_dir("XDG_DATA_HOME", ".local/share")
XDG_STATE_HOME = _get_xdg_dir("XDG_STATE_HOME", ".local/state")
XDG_CACHE_HOME = _get_xdg_dir("XDG_CACHE_HOME", ".cache")
XDG_CONFIG_HOME = _get_xdg_dir("XDG_CONFIG_HOME", ".config")

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
