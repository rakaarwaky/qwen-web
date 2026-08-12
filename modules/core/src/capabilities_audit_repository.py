"""Capabilities: audit log repository and workspace init (AES403).

Implements IFileSystemProtocol — structured JSONL audit history, error traces,
step-level context, workspace initialization, and audit-log reads. All file
system I/O for the domain lives here.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.shared.src.contract_core_protocol import IFileSystemProtocol
from modules.shared.src.taxonomy_core_constant import (
    BASE_DIR,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_TODO,
    XDG_SKILL_MD,
)
from modules.shared.src.taxonomy_core_vo import RunContext


class AuditRepository(IFileSystemProtocol):
    """Structured JSONL audit log with error traces and step-level context."""

    def __init__(self, log_dir: Path | None = None) -> None:
        """Initialize audit log files in the target directory."""
        target_dir = log_dir or DEFAULT_LOG
        target_dir.mkdir(parents=True, exist_ok=True)
        self._audit = target_dir / "audit_history.jsonl"
        self._errors = target_dir / "errors.log"
        self._errors_jsonl = target_dir / "errors.jsonl"

    def log_step(
        self,
        ctx: RunContext,
        step: str,
        src: str,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log granular step-by-step event execution for end-to-end traceability."""
        rec: dict[str, Any] = {
            "run_id": ctx.run_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "event": "step_execution",
            "step": step,
            "source_file": src,
            "status": status,
        }
        if details is not None:
            rec["details"] = details
        with self._audit.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def log(
        self,
        status: str,
        ctx: RunContext,
        src: str,
        dst: str,
        dur: float,
        in_c: int,
        out_c: int,
        err: str = "",
    ) -> None:
        """Log a completed file processing result with duration and character counts."""
        rec = {
            "run_id": ctx.run_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "source_file": src,
            "output_file": dst,
            "status": status,
            "duration_sec": dur,
            "input_chars": in_c,
            "output_chars": out_c,
        }
        if err:
            rec["error"] = err
        with self._audit.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if err:
            err_entry = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [run_id={ctx.run_id}] {src}: {err}\n\n"
            with self._errors.open("a", encoding="utf-8") as f:
                f.write(err_entry)

            err_json_rec = {
                "run_id": ctx.run_id,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "source_file": src,
                "output_file": dst,
                "error": err,
                "duration_sec": dur,
                "input_chars": in_c,
            }
            with self._errors_jsonl.open("a", encoding="utf-8") as f:
                f.write(json.dumps(err_json_rec, ensure_ascii=False) + "\n")

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

        links = {
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

    def get_audit_log(self, limit: int = 20) -> str:
        """Fetch recent entries from the JSONL audit trail log."""
        audit_file = self._audit
        if not audit_file.exists():
            return "Audit log file does not exist yet."

        lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
        recent = lines[-limit:]
        records: list[Any] = [json.loads(line) for line in recent if line.strip()]
        return json.dumps(records, indent=2)
