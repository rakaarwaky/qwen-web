"""Time formatter utility.

Utility layer (utility_core_time_formatter): UTC timestamp formatting.
Stateless function consumed by AuditRepository, Saver, and other Capabilities.
Taxonomy layer import only.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return current UTC time as an ISO-format string.

    Returns
    -------
    str
        ISO 8601 formatted timestamp with UTC timezone.

    """
    return datetime.now(tz=timezone.utc).isoformat()
