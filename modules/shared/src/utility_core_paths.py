"""OS-specific path resolution utilities.

Utility layer (utility_core_paths): stateless functions for computing XDG,
application, and Playwright browser paths. Taxonomy imports only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _get_os_data_home() -> Path:
    if os.environ.get("XDG_DATA_HOME"):
        return Path(os.environ["XDG_DATA_HOME"]) / "qwen-web"
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_appdata) / "qwen-web"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "qwen-web"
    return Path.home() / ".local/share/qwen-web"


def _get_os_state_home() -> Path:
    if os.environ.get("XDG_STATE_HOME"):
        return Path(os.environ["XDG_STATE_HOME"]) / "qwen-web"
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_appdata) / "qwen-web" / "state"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "qwen-web"
    return Path.home() / ".local/state/qwen-web"


def _get_os_cache_home() -> Path:
    if os.environ.get("XDG_CACHE_HOME"):
        return Path(os.environ["XDG_CACHE_HOME"]) / "qwen-web"
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_appdata) / "qwen-web" / "cache"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "qwen-web"
    return Path.home() / ".cache/qwen-web"


def _get_os_config_home() -> Path:
    if os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]) / "qwen-web"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "qwen-web"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "qwen-web"
    return Path.home() / ".config/qwen-web"


def get_playwright_browsers_path() -> Path:
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        env_path = os.environ["PLAYWRIGHT_BROWSERS_PATH"]
        if env_path != "0":
            return Path(env_path)
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_appdata) / "ms-playwright"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"
    return Path.home() / ".cache/ms-playwright"


# ─── Computed application paths (evaluated at import time) ──────────────
XDG_DATA_HOME = _get_os_data_home()
XDG_STATE_HOME = _get_os_state_home()
XDG_CACHE_HOME = _get_os_cache_home()
XDG_CONFIG_HOME = _get_os_config_home()

DEFAULT_OUTPUT = XDG_DATA_HOME / "output"
DEFAULT_LOG = XDG_STATE_HOME / "log"
DEFAULT_SESSION = XDG_DATA_HOME / "qwen_session"
XDG_SKILL_MD = XDG_DATA_HOME / "SKILL.md"


__all__ = [
    "_get_os_data_home",
    "_get_os_state_home",
    "_get_os_cache_home",
    "_get_os_config_home",
    "get_playwright_browsers_path",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "XDG_CACHE_HOME",
    "XDG_CONFIG_HOME",
    "DEFAULT_OUTPUT",
    "DEFAULT_LOG",
    "DEFAULT_SESSION",
    "XDG_SKILL_MD",
]
