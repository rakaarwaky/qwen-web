"""Root: CLI container entry point.

Instantiates and wires SharedContainer for CLI surface.
"""

from __future__ import annotations

from modules.core.src.root_core_container import SharedContainer


def create_cli_container() -> SharedContainer:
    """Instantiate and wire SharedContainer for CLI surface."""
    container = SharedContainer(use_linux_guard=True)
    container.wire()
    return container


__all__ = ["SharedContainer", "create_cli_container"]
