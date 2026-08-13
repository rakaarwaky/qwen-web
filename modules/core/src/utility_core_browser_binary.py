"""Chrome binary discovery utilities.

Utility layer (utility_core_browser_binary): stateless functions for locating
a Chromium-based browser binary on the host.
"""

from __future__ import annotations

import shutil

CHROME_CANDIDATES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)


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
    return ""
