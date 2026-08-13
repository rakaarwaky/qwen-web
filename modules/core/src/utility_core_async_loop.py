"""Async event-loop isolation utilities.

Utility layer (utility_core_async_loop): stateless functions for event-loop
management in worker threads that host Playwright sync APIs.
"""

from __future__ import annotations

import asyncio


def isolate_thread_event_loop() -> None:
    """Ensure the current thread has an isolated event loop for sync APIs.

    Clears any running loop bound to the thread and installs a fresh one so
    Playwright sync_api calls do not collide with a foreign loop.
    """
    try:
        if hasattr(asyncio, "_set_running_loop"):
            asyncio._set_running_loop(None)
    except (RuntimeError, AttributeError):
        pass

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except RuntimeError:
        pass
