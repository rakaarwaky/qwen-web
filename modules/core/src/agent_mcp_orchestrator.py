"""Agent: MCP feature orchestrator (AES405).

Implements IMcpAggregate — delegates tool operations to the core orchestrator.
The thread event-loop isolation pattern lives here so Playwright's sync API
works inside the MCP worker thread.
"""

from __future__ import annotations

import asyncio

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.contract_mcp_aggregate import IMcpAggregate


def isolate_thread_event_loop() -> None:
    """Ensure the worker thread has an isolated event loop for Playwright sync_api."""
    try:
        if hasattr(asyncio, "_set_running_loop"):
            asyncio._set_running_loop(None)
    except Exception:
        pass
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception:
        pass


class McpOrchestrator(IMcpAggregate):
    """MCP tool handlers delegating to the core aggregate."""

    def __init__(self, core: ICoreAggregate) -> None:
        """Inject the core aggregate."""
        self._core = core

    def send_prompt(self, prompt: str, timeout_sec: int = 120, headless: bool = True) -> str:
        """Send a direct text prompt."""
        isolate_thread_event_loop()
        return self._core.send_prompt(prompt, timeout_sec, headless)

    def process_single(
        self,
        input_file: str,
        output_file: str | None = None,
        headless: bool = True,
    ) -> str:
        """Process a single file."""
        isolate_thread_event_loop()
        return self._core.process_single_file(input_file, output_file, headless)

    def process_batch(
        self,
        input_dir: str | None = None,
        output_dir: str | None = None,
        headless: bool = True,
    ) -> str:
        """Process a batch directory."""
        isolate_thread_event_loop()
        return self._core.process_batch(input_dir, output_dir, headless)

    def start_watcher(self, interval_sec: int = 3, headless: bool = True) -> str:
        """Run the folder watcher."""
        isolate_thread_event_loop()
        return self._core.process_watcher(interval_sec, headless)

    def setup_session(self) -> str:
        """Manual login / session setup."""
        isolate_thread_event_loop()
        return self._core.setup_session()

    def get_audit_log(self, limit: int = 20) -> str:
        """Fetch audit log entries."""
        return self._core.get_audit_log(limit)
