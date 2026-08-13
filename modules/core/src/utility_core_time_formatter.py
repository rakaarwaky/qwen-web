"""Time formatter utility (core re-export).

Re-export from shared layer to avoid import breakage.
The canonical implementation lives in modules/shared/src/utility_core_time_formatter.py.
"""

from __future__ import annotations

from modules.shared.src.utility_core_time_formatter import utc_now_iso

__all__ = ["utc_now_iso"]
