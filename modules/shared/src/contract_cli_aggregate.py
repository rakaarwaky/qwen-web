"""CLI aggregate contract — init, interactive prompt, manual login.

Taxonomy layer (contract(aggregate)): depends only on taxonomy + contract(protocol).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from modules.shared.src.taxonomy_config_vo import AppConfig


class ICliAggregate(ABC):
    """CLI-specific aggregate (init, interactive, login)."""

    @abstractmethod
    def init_workspace(self, target_dir: Path | str = ".") -> None:
        """Initialize the workspace (.agents/skills + .qwen-web symlinks)."""

    @abstractmethod
    def interactive_prompt(self) -> AppConfig | None:
        """Display the interactive TUI and build an AppConfig."""

    @abstractmethod
    def run_manual_login(self, cfg: AppConfig) -> None:
        """Open a visible browser for manual login."""


__all__ = ["ICliAggregate", "AppConfig"]
