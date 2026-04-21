from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.logging_setup import setup_logging
from src.runtime_paths import project_root
from src.ui.controller import UiController
from src.ui.facade import UiFacade
from src.ui.resources import app_icon_path
from src.ui.state import SessionStatus
from src.ui.styles import load_stylesheet
from src.ui.widgets.login_panel import LoginWindow
from src.ui.window import MainWindow


def _write_startup_crash(traceback_text: str) -> None:
    try:
        log_dir = project_root() / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        crash_log = log_dir / "ui-startup-crash.log"
        with crash_log.open("a", encoding="utf-8") as handle:
            handle.write(traceback_text)
            if not traceback_text.endswith("\n"):
                handle.write("\n")
            handle.write("\n")
    except OSError:
        pass


class AppCoordinator:
    def __init__(self, facade: UiFacade) -> None:
        self._facade = facade
        self._window = None

    def _default_profile_name(self) -> str:
        profiles = self._facade.list_profiles()
        if profiles:
            return profiles[0].name
        return "default"

    def _swap_window(self, window) -> None:
        previous = self._window
        self._window = window
        window.show()
        if previous is not None:
            previous.close()
            previous.deleteLater()

    def show_login(self, profile_name: str | None = None) -> None:
        window = LoginWindow(
            self._facade,
            controller=UiController(self._facade),
            initial_profile_name=profile_name or self._default_profile_name(),
            show_on_init=False,
        )
        window.authenticated.connect(self.show_home)
        self._swap_window(window)

    def show_home(self, profile_name: str, initial_session_state=None) -> None:
        window = MainWindow(
            self._facade,
            controller=UiController(self._facade),
            initial_profile_name=profile_name,
            initial_session_state=initial_session_state,
            show_on_init=False,
        )
        window.loginRequired.connect(self.show_login)
        self._swap_window(window)

    def start(self) -> None:
        profile_name = self._default_profile_name()
        state = self._facade.get_session_state(profile_name)
        if state.status is SessionStatus.AUTHENTICATED:
            self.show_home(profile_name, initial_session_state=state)
            return
        self.show_login(profile_name)


def main() -> None:
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "cocoa"))
        setup_logging()
        app = QApplication(sys.argv)
        app.setApplicationName("CGYY Workbench")
        icon_path = app_icon_path()
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
        app.setStyleSheet(load_stylesheet())
        facade = UiFacade()
        coordinator = AppCoordinator(facade)
        coordinator.start()
        sys.exit(app.exec())
    except BaseException:
        _write_startup_crash(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
