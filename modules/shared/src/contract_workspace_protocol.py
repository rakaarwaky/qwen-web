"""Workspace provisioning protocol (contract layer).

Taxonomy layer (contract(protocol)): pure ABC, signatures use VOs.
Capabilities implement these; agents/surfaces depend on them via DI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class IWorkspaceProtocol(ABC):
    """Workspace directory provisioning capability contract."""

    @abstractmethod
    def init_workspace(self, target_dir: Path) -> None:
        """Initialize workspace directories, SKILL.md, symlinks, and .gitignore."""


__all__ = ["IWorkspaceProtocol"]
