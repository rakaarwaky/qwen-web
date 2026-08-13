"""Capabilities: workspace provisioner (AES403).

Implements IWorkspaceProtocol — workspace initialization with XDG directories,
SKILL.md provisioning, .qwen-web symlinks, and .gitignore management.
All file system I/O for workspace setup lives here.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from modules.shared.src.contract_workspace_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_core_constant import (
    BASE_DIR,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_TODO,
    XDG_SKILL_MD,
)


# Block 1: Class Definition & Constructor


class WorkspaceProvisioner(IWorkspaceProtocol):
    """Workspace directory provisioning with symlinks and .gitignore management."""

    def __init__(self) -> None:
        """Initialize WorkspaceProvisioner."""
        pass

    # ─── Block 2: Public Contract (IWorkspaceProtocol ONLY) ──
    def init_workspace(self, target_dir: Path) -> None:
        """Initialize workspace with .agents/skills/qwen-web/SKILL.md, .qwen-web symlinks, and .gitignore."""
        target_path = target_dir.resolve()

        # 1. Ensure XDG directories exist
        DEFAULT_TODO.mkdir(parents=True, exist_ok=True)
        DEFAULT_OUTPUT.mkdir(parents=True, exist_ok=True)
        DEFAULT_LOG.mkdir(parents=True, exist_ok=True)

        # 2. Create .agents/skills/qwen-web/SKILL.md
        skills_dir = target_path / ".agents" / "skills" / "qwen-web"
        skills_dir.mkdir(parents=True, exist_ok=True)
        skill_md_dest = skills_dir / "SKILL.md"

        pkg_skill_md = BASE_DIR / "SKILL.md"
        if XDG_SKILL_MD.exists():
            shutil.copy2(XDG_SKILL_MD, skill_md_dest)
        elif pkg_skill_md.exists():
            shutil.copy2(pkg_skill_md, skill_md_dest)
        else:
            skill_content = (
                "---\n"
                "name: qwen-web\n"
                "description: Automate Qwen AI Web (chat.qwen.ai) prompt processing via CLI or MCP tools.\n"
                "---\n"
                "# Qwen Web Automation Skill Guide\n"
            )
            skill_md_dest.write_text(skill_content, encoding="utf-8")

        # 3. Create .qwen-web directory with symlinks to XDG paths
        dot_qwen = target_path / ".qwen-web"
        dot_qwen.mkdir(parents=True, exist_ok=True)

        links: dict[str, Any] = {
            "log": DEFAULT_LOG,
            "input": DEFAULT_TODO,
            "output": DEFAULT_OUTPUT,
        }

        for link_name, xdg_target in links.items():
            link_path = dot_qwen / link_name
            if link_path.is_symlink() or link_path.exists():
                if link_path.is_dir() and not link_path.is_symlink():
                    continue
                link_path.unlink(missing_ok=True)

            if not link_path.exists() and not link_path.is_symlink():
                try:
                    os.symlink(xdg_target, link_path, target_is_directory=True)
                except OSError:
                    continue

        # 4. Add .qwen-web/ to .gitignore
        git_ignore = target_path / ".gitignore"
        entry = ".qwen-web/"
        if git_ignore.exists():
            content = git_ignore.read_text(encoding="utf-8")
            if entry not in content and ".qwen-web" not in content:
                if content and not content.endswith("\n"):
                    content += "\n"
                content += f"{entry}\n"
                git_ignore.write_text(content, encoding="utf-8")
        else:
            git_ignore.write_text(f"{entry}\n", encoding="utf-8")

    # ─── Block 3: Dunder Methods, Factories & Helpers ─────

    def __repr__(self) -> str:
        """Return string representation of WorkspaceProvisioner."""
        return "WorkspaceProvisioner()"
