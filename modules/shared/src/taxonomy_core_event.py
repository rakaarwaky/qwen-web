"""Lifecycle event bus for pipeline events.

Taxonomy layer (taxonomy(event)): immutable event payloads, logger injected via
constructor to keep the layer free of capability/observability imports.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from modules.shared.src.taxonomy_core_vo import (
    EVENT_DESCRIPTIONS,
    LifecycleEvent,
    QwenEventType,
)


class LifecycleEmitter:
    """Simple event bus for pipeline lifecycle events with typed dispatcher capability."""

    def __init__(self, logger: Any | None = None) -> None:
        """Initialize with an empty callback registry and an optional logger."""
        self._callbacks: dict[str, list[Any]] = {}
        self._logger = logger or logging.getLogger("lifecycle")

    def on(self, event_name: QwenEventType | str, callback: Any) -> None:
        """Register a callback for a named lifecycle event."""
        key = str(event_name)
        self._callbacks.setdefault(key, []).append(callback)

    def emit(self, event_name: QwenEventType | str, details: dict[str, Any] | None = None) -> LifecycleEvent:
        """Emit a lifecycle event to all registered callbacks."""
        key = str(event_name)
        evt = LifecycleEvent(
            name=key,
            timestamp=time.time(),
            details=details or {},
        )
        enum_member = event_name if isinstance(event_name, QwenEventType) else None
        label = EVENT_DESCRIPTIONS.get(enum_member, key) if enum_member else key
        detail_str = f" - {details}" if details else ""
        self._logger.info(f"[{key}] {label}{detail_str}")
        for cb in self._callbacks.get(key, []):
            try:
                cb(evt)
            except Exception as exc:
                self._logger.warning(f"lifecycle_callback_error event={key} error={exc}")
        return evt
