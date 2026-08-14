"""CLI surface: Textual-based Session Setup submenu."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static


class SessionSetupScreen(Screen):
    """Session setup submenu with status and actions."""

    def __init__(self, status_text: str, on_login, on_back) -> None:
        super().__init__()
        self.status_text = status_text
        self.on_login = on_login
        self.on_back = on_back

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self.status_text, id="session_status"),
            Button("Delete Session & Login Again", id="login"),
            Button("Back to Main Menu", id="back"),
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "login":
            self.on_login()
            self.app.exit("login")
        elif event.button.id == "back":
            self.on_back()
            self.app.exit("back")


class SessionSetupApp(App):
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

    def __init__(self, status_text: str, on_login, on_back) -> None:
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


def run_session_setup(status_text: str, on_login, on_back) -> str:
    """Run the Textual session setup submenu and return the selected action."""
    app = SessionSetupApp(status_text, on_login, on_back)
    app.run()
    return app.result
