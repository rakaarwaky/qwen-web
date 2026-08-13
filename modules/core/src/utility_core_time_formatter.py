"""Time formatter utility (core module).

UTC timestamp formatting — stateless, taxonomy-only. Provides `utc_now_iso`
for AuditRepository, Saver, and other Capabilities in this module.
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


__all__ = ["utc_now_iso"]
