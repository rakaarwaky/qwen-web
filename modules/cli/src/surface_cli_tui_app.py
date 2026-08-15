"""Modern-Brutalist TUI interactive controller matching Obsidian Nebula design system.

Surface layer (surface_cli): Textual application for interactive prompt execution,
attachment selection, live logging, and session setup.
"""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
    Switch,
)

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import AppConfig
from modules.shared.src.taxonomy_core_constant import DEFAULT_OUTPUT
from modules.shared.src.taxonomy_core_vo import FilePath

TUI_CSS = """
/* ─── Obsidian Nebula Theme Colors ────────────────────────── */
Screen {
    background: #051424;
    color: #d5e4fa;
    layers: base modal;
}

Header {
    background: #051424;
    color: #c0c1ff;
    border-bottom: solid #464554;
    height: 3;
    dock: top;
}

Footer {
    background: #c0c1ff;
    color: #1000a9;
    height: 1;
    dock: bottom;
}

#main-container {
    height: 1fr;
    width: 100%;
    layout: horizontal;
    background: #051424;
}

/* ─── Left Pane: Execution Form ───────────────────────────── */
#left-pane {
    width: 50%;
    height: 100%;
    background: #010f1f;
    border-right: solid #464554;
    padding: 1 2;
}

.pane-title {
    background: #051424;
    color: #c0c1ff;
    text-style: bold;
    padding: 0 1;
    margin-bottom: 1;
    border-bottom: solid #464554;
    height: 3;
}

.field-block {
    margin-bottom: 1;
    height: auto;
}

.field-label {
    color: #d5e4fa;
    text-style: bold;
    margin-bottom: 0;
}

.field-row {
    layout: horizontal;
    height: 3;
    margin-bottom: 1;
}

.field-input {
    width: 1fr;
    background: #122031;
    border: solid #464554;
    color: #d5e4fa;
}

.field-input:focus {
    border: solid #c0c1ff;
}

.btn-browse {
    width: 10;
    min-width: 10;
    margin-left: 1;
    background: #1d2b3c;
    color: #c0c1ff;
    border: solid #464554;
}

.btn-browse:hover {
    background: #283647;
    border: solid #c0c1ff;
}

.toggle-row {
    layout: horizontal;
    height: 3;
    background: #122031;
    border: solid #464554;
    padding: 0 1;
    margin-bottom: 1;
    align: left middle;
}

.toggle-label-box {
    width: 1fr;
}

.toggle-subtext {
    color: #908fa0;
}

Switch {
    background: #283647;
}

Switch.-on {
    background: #8083ff;
}

.timeout-input {
    width: 12;
    background: #051424;
    border: solid #464554;
    color: #d5e4fa;
    text-align: right;
}

#btn-run {
    width: 100%;
    height: 3;
    background: #c0c1ff;
    color: #1000a9;
    border: solid #c0c1ff;
    text-style: bold;
    margin-top: 1;
}

#btn-run:hover {
    background: #051424;
    color: #c0c1ff;
}

/* ─── Right Pane: Live Log & Monitor ──────────────────────── */
#right-pane {
    width: 50%;
    height: 100%;
    background: #0e1c2d;
    padding: 1 2;
}

#log-view {
    height: 1fr;
    background: #051424;
    border: solid #464554;
    color: #d5e4fa;
    padding: 1;
}

#status-badge {
    color: #10B981;
    text-style: bold;
}

/* ─── Modal File Picker ───────────────────────────────────── */
FilePickerModal {
    align: center middle;
    background: rgba(5, 20, 36, 0.85);
}

#modal-container {
    width: 70%;
    height: 70%;
    background: #0e1c2d;
    border: solid #c0c1ff;
    padding: 1 2;
}

#modal-tree {
    height: 1fr;
    background: #051424;
    border: solid #464554;
    margin: 1 0;
}
"""


class FilePickerModal(ModalScreen[str | None]):
    """Modal screen for visual file picking using DirectoryTree."""

    def __init__(self, start_path: Path | None = None) -> None:
        super().__init__()
        self._start_path = start_path or Path.cwd()

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label("[ SELECT FILE ]", classes="field-label")
            yield DirectoryTree(str(self._start_path), id="modal-tree")
            with Horizontal():
                yield Button("Cancel", id="btn-cancel-modal", classes="btn-browse")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.dismiss(str(event.path))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel-modal":
            self.dismiss(None)


class QwenTuiApp(App[None]):
    """Obsidian Nebula Terminal User Interface for Qwen Web Automation."""

    CSS = TUI_CSS
    TITLE = "QWEN-CLI V1.0.4 • OBSIDIAN NEBULA"
    SUB_TITLE = "chat.qwen.ai automation engine"

    BINDINGS = [
        Binding("enter", "run_action", "Run", priority=True),
        Binding("ctrl+l", "login_action", "Login"),
        Binding("ctrl+i", "init_action", "Init"),
        Binding("ctrl+r", "reset_action", "Reset"),
        Binding("escape", "quit", "Exit"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, core: ICoreAggregate) -> None:
        super().__init__()
        self._core = core
        self._target_field_for_picker: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            # ─── Left Pane: Config ──────────────────────────────
            with ScrollableContainer(id="left-pane"):
                yield Static("[ EXECUTION CONFIGURATION ]", classes="pane-title")

                # Prompt file
                yield Label("Prompt File (Required) *", classes="field-label")
                with Horizontal(classes="field-row"):
                    yield Input(placeholder="path/to/prompt.md", id="input-prompt", classes="field-input")
                    yield Button("Browse", id="btn-browse-prompt", classes="btn-browse")

                # Attachment file
                yield Label("Attachment File (Optional)", classes="field-label")
                with Horizontal(classes="field-row"):
                    yield Input(placeholder="path/to/attachment.file", id="input-file", classes="field-input")
                    yield Button("Browse", id="btn-browse-file", classes="btn-browse")

                # Output path
                yield Label("Output Destination", classes="field-label")
                with Horizontal(classes="field-row"):
                    yield Input(
                        value=str(DEFAULT_OUTPUT),
                        placeholder="path/to/output.md",
                        id="input-output",
                        classes="field-input",
                    )
                    yield Button("Browse", id="btn-browse-output", classes="btn-browse")

                # Toggles
                with Horizontal(classes="toggle-row"):
                    with Vertical(classes="toggle-label-box"):
                        yield Label("Headless Browser", classes="field-label")
                        yield Label("Run automation in background without browser UI", classes="toggle-subtext")
                    yield Switch(value=True, id="switch-headless")

                with Horizontal(classes="toggle-row"):
                    with Vertical(classes="toggle-label-box"):
                        yield Label("Inline Prompt Only", classes="field-label")
                        yield Label("Inject file text directly instead of uploading", classes="toggle-subtext")
                    yield Switch(value=False, id="switch-inline")

                with Horizontal(classes="toggle-row"):
                    yield Label("Timeout (seconds)", classes="field-label")
                    yield Input(value="120", id="input-timeout", classes="timeout-input")

                yield Button("⚡ RUN AUTOMATION [Enter]", variant="primary", id="btn-run")

            # ─── Right Pane: Log Monitor ────────────────────────
            with Vertical(id="right-pane"):
                with Horizontal(classes="pane-title"):
                    yield Label("[ PREVIEW & LIVE LOG ]", classes="field-label")
                    yield Label("STATUS: READY", id="status-badge")
                yield RichLog(id="log-view", highlight=True, markup=True)

        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#log-view", RichLog)
        log.write("[bold #c0c1ff]Qwen Web Automation CLI initialized.[/]")
        log.write("[#908fa0]Ready for prompt dispatch. Fill fields on the left and hit Enter.[/]\n")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "btn-run":
            self.action_run_action()
        elif button_id == "btn-browse-prompt":
            self._open_picker("input-prompt")
        elif button_id == "btn-browse-file":
            self._open_picker("input-file")
        elif button_id == "btn-browse-output":
            self._open_picker("input-output")

    def _open_picker(self, target_input_id: str) -> None:
        self._target_field_for_picker = target_input_id

        def _on_picked(path: str | None) -> None:
            if path and self._target_field_for_picker:
                field = self.query_one(f"#{self._target_field_for_picker}", Input)
                field.value = path

        self.push_screen(FilePickerModal(), _on_picked)

    def action_run_action(self) -> None:
        prompt_val = self.query_one("#input-prompt", Input).value.strip()
        if not prompt_val:
            self._log_msg("[bold #EF4444]ERROR:[/] Prompt file is required.")
            return

        p_path = Path(prompt_val).resolve()
        if not p_path.exists():
            self._log_msg(f"[bold #EF4444]ERROR:[/] Prompt file not found: {prompt_val}")
            return

        file_val = self.query_one("#input-file", Input).value.strip()
        f_path = Path(file_val).resolve() if file_val else None
        if f_path and not f_path.exists():
            self._log_msg(f"[bold #EF4444]ERROR:[/] Attachment file not found: {file_val}")
            return

        out_val = self.query_one("#input-output", Input).value.strip()
        out_path = Path(out_val).resolve() if out_val else DEFAULT_OUTPUT

        headless_val = self.query_one("#switch-headless", Switch).value
        inline_val = self.query_one("#switch-inline", Switch).value
        try:
            timeout_val = int(self.query_one("#input-timeout", Input).value.strip() or "120")
        except ValueError:
            timeout_val = 120

        cfg = AppConfig(
            mode="single",
            input_path=p_path,
            output_path=out_path,
            prompt_file=p_path,
            prompt_path=p_path,
            file_path=f_path,
            headless=headless_val,
            inline_prompt=inline_val,
            request_timeout=timeout_val,
        )

        self._execute_worker(cfg)

    @work(thread=True)
    def _execute_worker(self, cfg: AppConfig) -> None:
        badge = self.query_one("#status-badge", Label)
        badge.update("STATUS: RUNNING")
        self._log_msg(f"[bold #c0c1ff]>>> Starting automation for: {cfg.prompt_path.name}[/]")  # type: ignore[union-attr]
        if cfg.file_path:
            self._log_msg(f"[#b9c8dd]    Attaching: {cfg.file_path.name}[/]")
        self._log_msg(f"[#908fa0]    Headless: {cfg.headless} | Timeout: {cfg.request_timeout}s[/]")

        try:
            res = self._core.process_mode(cfg)
            self._log_msg(f"[bold #10B981]SUCCESS:[/] {res}")
        except Exception as exc:
            self._log_msg(f"[bold #EF4444]FAILED:[/] {exc}")
        finally:
            badge.update("STATUS: READY")

    def action_login_action(self) -> None:
        self._log_msg("[bold #c0c1ff]>>> Launching interactive session setup...[/]")
        self._login_worker()

    @work(thread=True)
    def _login_worker(self) -> None:
        try:
            res = self._core.setup_session()
            self._log_msg(f"[bold #10B981]LOGIN RESULT:[/] {res}")
        except Exception as exc:
            self._log_msg(f"[bold #EF4444]LOGIN FAILED:[/] {exc}")

    def action_init_action(self) -> None:
        try:
            self._core.init_workspace(FilePath(str(Path.cwd())))
            self._log_msg(f"[bold #10B981]INIT:[/] Workspace initialized in {Path.cwd()}")
        except Exception as exc:
            self._log_msg(f"[bold #EF4444]INIT ERROR:[/] {exc}")

    def action_reset_action(self) -> None:
        self.query_one("#input-prompt", Input).value = ""
        self.query_one("#input-file", Input).value = ""
        self.query_one("#input-output", Input).value = str(DEFAULT_OUTPUT)
        self._log_msg("[#908fa0]Form reset to defaults.[/]")

    def _log_msg(self, msg: str) -> None:
        log = self.query_one("#log-view", RichLog)
        log.write(msg)
