"""Root: MCP feature DI container.

Uses SharedContainer from root_core_container.py — the single wiring for both
CLI and MCP features. Only imports from root_core_container.py.
"""

from __future__ import annotations

from modules.core.src.root_core_container import SharedContainer


class McpContainer(SharedContainer):
    """Dependency injection container for the MCP feature."""

    def __init__(
        self,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_window: int = 30,
        rate_limit_per_minute: int = 60,
    ) -> None:
        super().__init__(
            use_linux_guard=False,
            circuit_breaker_threshold=circuit_breaker_threshold,
            circuit_breaker_window=circuit_breaker_window,
            rate_limit_per_minute=rate_limit_per_minute,
        )


def create_mcp_feature() -> McpContainer:
    """Factory returning a fully wired MCP container."""
    container = McpContainer()
    container.wire()
    return container
