"""Agent: CLI feature orchestrator (AES405).

Implements ICliAggregate — workspace init, interactive TUI prompt building,
and manual login orchestration. TUI presentation details stay in the surface;
this layer only provides the action steps.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from modules.shared.src.contract_cli_aggregate import ICliAggregate
from modules.shared.src.contract_core_protocol import IBrowserProtocol
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import (
    BASE_DIR,
    CHAT_URL,
    DEFAULT_DONE,
    DEFAULT_FAILED,
    DEFAULT_LOG,
    DEFAULT_OUTPUT,
    DEFAULT_PROC,
    DEFAULT_SESSION,
    DEFAULT_TODO,
    XDG_SKILL_MD,
)
from modules.shared.src.utility_core_path import list_input_files


def _base_config(mode: str, headless: bool = False) -> AppConfig:
    """Build an AppConfig with default XDG paths."""
    return AppConfig(
        mode=mode,
        input_path=DEFAULT_TODO,
        output_path=DEFAULT_OUTPUT,
        done_path=DEFAULT_DONE,
        failed_path=DEFAULT_FAILED,
        proc_path=DEFAULT_PROC,
        session_path=DEFAULT_SESSION,
        log_path=DEFAULT_LOG,
        headless=headless,
    )


class CliOrchestrator(ICliAggregate):
    """CLI-specific orchestration: init, interactive prompt, manual login."""

    def __init__(self, browser: IBrowserProtocol, log_fn: Callable[..., Any] | None = None) -> None:
        """Inject the browser capability used for manual login."""
        self._browser = browser
        self._log: Callable[..., Any] = log_fn or (lambda *_args, **_kwargs: None)

    def init_workspace(self, target_dir: Path | str = ".") -> None:
        """Initialize workspace with .agents/skills/qwen-web/SKILL.md, .qwen-web symlinks, and .gitignore."""
        target_path = Path(target_dir).resolve()
        print(f"\n[INIT] Initializing qwen-web environment in: {target_path}\n")

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

        try:
            rel_skill = skill_md_dest.relative_to(target_path)
        except ValueError:
            rel_skill = skill_md_dest
        print(f"  [OK] Created skill definition: {rel_skill}")

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
                    pass
                else:
                    link_path.unlink(missing_ok=True)

            if not link_path.exists() and not link_path.is_symlink():
                try:
                    os.symlink(xdg_target, link_path, target_is_directory=True)
                    print(f"  [LINK] Symlinked .qwen-web/{link_name} -> {xdg_target}")
                except Exception as e:
                    print(f"  [WARNING] Could not create symlink .qwen-web/{link_name}: {e}")

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
                print(f"  [FILE] Added {entry} to existing .gitignore")
            else:
                print(f"  [INFO] {entry} already present in .gitignore")
        else:
            git_ignore.write_text(f"{entry}\n", encoding="utf-8")
            print(f"  [FILE] Created .gitignore with {entry}")

        print("\n[DONE] Workspace initialization complete!\n")

    def interactive_prompt(self) -> AppConfig | None:
        """Display interactive TUI menu and build AppConfig from user selections."""
        if not sys.stdin.isatty():
            print("[ERROR] Interactive mode requires a TTY. Please provide CLI arguments.", file=sys.stderr)
            return None

        print("\n╭─ qwen-cli interactive setup ─────────────────────╮")
        print("│ 1. Watcher Mode (continuous)                     │")
        print("│ 2. Batch Mode (folder)                           │")
        print("│ 3. Single File Mode                              │")
        print("│ 4. Manual Login / Session Setup                  │")
        print("│ 5. Initialize Workspace (.agents/skills & .qwen) │")
        print("│ 6. Exit                                          │")
        print("╰──────────────────────────────────────────────────╯")

        choice = input("Select [1-6, default=1]: ").strip() or "1"
        if choice == "6":
            print("Goodbye!")
            return None

        if choice == "5":
            self.init_workspace(Path.cwd())
            return None

        if choice == "4":
            return _base_config("login", headless=False)

        headless = input("Run headless? [y/N, default=N]: ").strip().lower() == "y"
        mode_map: dict[str, Literal["watcher", "batch", "single", "login"]] = {
            "1": "watcher",
            "2": "batch",
            "3": "single",
        }
        mode: Literal["watcher", "batch", "single", "login"] = mode_map.get(choice, "watcher")

        if mode == "single":
            available_files = list_input_files(DEFAULT_TODO)
            if available_files:
                print("\n[FILES] Available input files:")
                for idx, (_abs_p, rel_p) in enumerate(available_files, 1):
                    print(f"  {idx}. {rel_p}")

                file_choice = input(f"Select input file [1-{len(available_files)}, default=1]: ").strip() or "1"
                try:
                    choice_idx = int(file_choice) - 1
                    if 0 <= choice_idx < len(available_files):
                        chosen_abs, _chosen_rel = available_files[choice_idx]
                    else:
                        chosen_abs, _chosen_rel = available_files[0]
                except ValueError:
                    chosen_abs, _chosen_rel = available_files[0]

                return AppConfig(
                    mode=mode,
                    input_path=chosen_abs,
                    output_path=DEFAULT_OUTPUT,
                    done_path=DEFAULT_DONE,
                    failed_path=DEFAULT_FAILED,
                    proc_path=DEFAULT_PROC,
                    session_path=DEFAULT_SESSION,
                    log_path=DEFAULT_LOG,
                    headless=headless,
                )
            else:
                input_file = input(f"Enter input file path [default: {DEFAULT_TODO}]: ").strip() or str(DEFAULT_TODO)
                output_file = input(f"Enter output file path [default: {DEFAULT_OUTPUT}]: ").strip() or str(DEFAULT_OUTPUT)
                return AppConfig(
                    mode=mode,
                    input_path=Path(input_file),
                    output_path=Path(output_file),
                    done_path=DEFAULT_DONE,
                    failed_path=DEFAULT_FAILED,
                    proc_path=DEFAULT_PROC,
                    session_path=DEFAULT_SESSION,
                    log_path=DEFAULT_LOG,
                    headless=headless,
                )

        return _base_config(mode, headless=headless)

    def run_manual_login(self, cfg: AppConfig) -> None:
        """Launch visible browser for interactive login and save session cookies."""
        if not sys.stdin.isatty():
            print("[ERROR] Manual login requires an interactive terminal (TTY).", file=sys.stderr)
            sys.exit(1)

        login_cfg = _base_config("login", headless=False)
        login_cfg = AppConfig(
            mode=login_cfg.mode,
            input_path=login_cfg.input_path,
            output_path=login_cfg.output_path,
            done_path=login_cfg.done_path,
            failed_path=login_cfg.failed_path,
            proc_path=login_cfg.proc_path,
            session_path=login_cfg.session_path,
            log_path=login_cfg.log_path,
            interval=cfg.interval,
            timeout=cfg.timeout,
            headless=False,
        )
        print(f"\n[LOGIN] Launching visible browser window on {CHAT_URL}...")
        with self._browser.browser_session(login_cfg) as bctx:
            page = bctx.pages[0] if bctx.pages else bctx.new_page()
            page.goto(CHAT_URL, wait_until="domcontentloaded")
            print("Please log in or resolve CAPTCHA in the browser window.")
            input("Press [ENTER] here once you have finished logging in: ")
            print(f"[OK] Session data successfully saved to '{login_cfg.session_path}'. You can now run in headless mode!\n")
