"""Chrome binary discovery utilities.

Utility layer (utility_core_browser_binary): stateless functions for locating
a Chromium-based browser binary on the host.
"""

from __future__ import annotations

import shutil

import os
import sys

CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "chrome",
    "chrome.exe",
    "msedge",
    "msedge.exe",
)

EXTRA_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_chrome_binary() -> str:
    """Return the path of the first available Chrome/Chromium binary, or ''.

    Returns
    -------
    str
        Absolute path to the discovered binary, or an empty string when none
        of the known candidates is installed.

    """
    for candidate in CHROME_CANDIDATES:
        path = shutil.which(candidate)
        if path:
            return path
    for extra in EXTRA_PATHS:
        if os.path.exists(extra):
            return extra
    return ""
