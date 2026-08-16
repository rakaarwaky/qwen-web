"""Root: MCP container entry point.

Instantiates and wires SharedContainer for MCP surface.
"""

from __future__ import annotations

from modules.core.src.root_core_container import SharedContainer


def create_mcp_container() -> SharedContainer:
    """Instantiate and wire SharedContainer for MCP surface."""
    container = SharedContainer()
    container.wire()
    return container


__all__ = ["SharedContainer", "create_mcp_container"]
