"""CLI surface: Textual-based Session Setup submenu."""

from __future__ import annotations

from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static


from textual.binding import Binding
from textual.screen import ModalScreen


class ConfirmModal(ModalScreen[bool]):
    """Modal screen asking confirmation for destructive actions."""

    BINDINGS = [Binding("escape", "dismiss_no", "Cancel")]

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self._title = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-modal-container"):
            yield Static(f"[bold red]{self._title.upper()}[/bold red]\n\n{self._message}\n")
            yield Button("Cancel", id="btn-cancel", variant="default")
            yield Button("Delete Session & Login", id="btn-confirm", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_dismiss_no(self) -> None:
        self.dismiss(False)


class SessionSetupScreen(Screen["SessionSetupApp"]):
    """Session setup submenu with status and actions."""

    def __init__(self, status_text: str, on_login: Callable[[], None], on_back: Callable[[], None]) -> None:
        super().__init__()
        self.status_text = status_text
        self.on_login = on_login
        self.on_back = on_back

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self.status_text, id="session_status"),
            Button("Delete Session & Login Again", id="login", variant="error"),
            Button("Back to Main Menu", id="back"),
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login":
            def _on_confirm(confirmed: bool | None) -> None:
                if confirmed:
                    self.on_login()
                    self.app.exit("login")

            msg = "Are you sure you want to delete your saved browser session?\nYou will need to log in again manually."
            self.app.push_screen(ConfirmModal("Confirm Session Reset", msg), _on_confirm)
        elif event.button.id == "back":
            self.on_back()
            self.app.exit("back")


class SessionSetupApp(App[str]):
    """Textual app for session setup submenu."""

    CSS = """
    Screen {
        align: center middle;
    }
    Vertical {
        width: 70;
        height: auto;
        border: solid green;
        padding: 1 2;
    }
    #session_status {
        width: 100%;
        margin-bottom: 1;
    }
    Button {
        width: 100%;
        margin: 1 0;
    }
    """

    def __init__(self, status_text: str, on_login: Callable[[], None], on_back: Callable[[], None]) -> None:
        super().__init__()
        self.status_text = status_text
        self.on_login = on_login
        self.on_back = on_back
        self.result = "back"

    def on_mount(self) -> None:
        self.push_screen(SessionSetupScreen(self.status_text, self.on_login, self.on_back))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login":
            self.on_login()
            self.result = "login"
        elif event.button.id == "back":
            self.on_back()
            self.result = "back"
        self.exit()


def run_session_setup(status_text: str, on_login: Callable[[], None], on_back: Callable[[], None]) -> str:
    """Run the Textual session setup submenu and return the selected action."""
    app = SessionSetupApp(status_text, on_login, on_back)
    app.run()
    return app.result
