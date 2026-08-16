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

from modules.core.src.utility_core_io_writer import ensure_dir
from modules.shared.src.contract_core_protocol import IWorkspaceProtocol
from modules.shared.src.taxonomy_core_constant import (
    BASE_DIR,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_SESSION,
    XDG_SKILL_MD,
)
from modules.shared.src.taxonomy_core_vo import FilePath

# Block 1: Class Definition & Constructor


class WorkspaceProvisioner(IWorkspaceProtocol):
    """Workspace directory provisioning with symlinks and .gitignore management."""

    def __init__(self) -> None:
        """Initialize WorkspaceProvisioner."""
        pass

    # ─── Block 2: Public Contract (IWorkspaceProtocol ONLY) ──
    def init_workspace(self, target_dir: FilePath) -> None:
        """Initialize workspace in 4 sequential steps:

        Step 1: Ensure XDG directories exist
        Step 2: Provision .agents/skills/qwen-web/SKILL.md
        Step 3: Provision .qwen-web directory with sample prompt/files & symlinks
        Step 4: Update .gitignore with .qwen-web/ entry
        """
        target_path = Path(str(target_dir)).resolve()

        # Step 1: Ensure XDG directories exist
        ensure_dir(DEFAULT_OUTPUT)
        ensure_dir(DEFAULT_LOG)

        # Step 2: Create .agents/skills/qwen-web/SKILL.md
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

        # Step 3: Create .qwen-web directory with symlinks to XDG paths
        dot_qwen = target_path / ".qwen-web"
        dot_qwen.mkdir(parents=True, exist_ok=True)

        dot_qwen_input = dot_qwen / "input"
        dot_qwen_input.mkdir(parents=True, exist_ok=True)

        prompt_sample = dot_qwen_input / "PROMPT.md"
        if not prompt_sample.exists():
            prompt_sample.write_text(
                "# Instruksi Pengujian Otomasi Qwen-Web\n\n"
                "Tolong analisis dokumen terlampir (`FILE.md`) dan "
                "berikan tanggapan komprehensif dengan struktur berikut:\n"
                "1. **Ringkasan Poin Utama** (3-5 poin penting dari dokumen)\n"
                "2. **Analisis Detail** (penjelasan mendalam mengenai isi dokumen)\n"
                "3. **Kesimpulan & Rekomendasi**\n\n"
                "Pastikan jawaban Anda terformat dengan Markdown yang rapi.\n",
                encoding="utf-8",
            )

        file_sample = dot_qwen_input / "FILE.md"
        if not file_sample.exists():
            file_sample.write_text(
                "# Dokumen Pengujian: Arsitektur & Performa Otomasi Web Qwen\n\n"
                "## 1. Latar Belakang & Pendahuluan\n"
                "Sistem otomasi antarmuka web Qwen dirancang untuk mengintegrasikan "
                "kapabilitas LLM dengan browser engine modern secara efisien.\n\n"
                "## 2. Fitur Utama yang Diuji\n"
                "- **Persistent Session Manager**: Menyimpan cookies dan data sesi Chromium.\n"
                "- **Event-Driven Observability**: Logging real-time terhubung ke TUI RichLog.\n"
                "- **Adaptive Send & Input Dispatcher**: Penanganan otomatis terhadap "
                "injeksi teks dan dokumen lampiran.\n\n"
                "## 3. Hasil Pengujian yang Diharapkan\n"
                "1. Berkas lampiran berhasil diunggah.\n"
                "2. Teks instruksi diinjeksi dengan tepat.\n"
                "3. Jawaban diekstrak secara utuh dan disimpan lokal.\n",
                encoding="utf-8",
            )

        links: dict[str, Any] = {
            "log": DEFAULT_LOG,
            "output": DEFAULT_OUTPUT,
            "qwen_session": DEFAULT_SESSION,
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

        # Step 4: Add .qwen-web/ to .gitignore
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
