from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from aris_control_2.app.gui_controller import GuiController, LoginResult
from aris_control_2.app.gui_views import LoginDialog, MainWindow


class GuiApp:
    def __init__(self, controller: GuiController | None = None) -> None:
        self.controller = controller or GuiController()
        self.root = tk.Tk()
        self.window = MainWindow(
            self.root,
            on_login=self.open_login,
            on_diagnostics=self.open_diagnostics,
            on_support=self.export_support,
            on_exit=self.root.destroy,
        )
        self._refresh_header()

    def run(self) -> None:
        self.root.mainloop()

    def _refresh_header(self) -> None:
        snapshot = self.controller.status_snapshot()
        self.window.set_header(
            connectivity=snapshot["connectivity"],
            base_url=snapshot["base_url"],
            version=snapshot["version"],
        )

    def open_login(self) -> None:
        dialog = LoginDialog(self.root, self._submit_login)
        dialog.wait()
        self._refresh_header()

    def _submit_login(self, username_or_email: str, password: str) -> LoginResult:
        return self.controller.login(username_or_email=username_or_email, password=password)

    def open_diagnostics(self) -> None:
        connectivity = self.controller.refresh_connectivity()
        self._refresh_header()
        text = self.controller.diagnostic_text()
        messagebox.showinfo(
            "Diagnóstico",
            f"Estado: {connectivity.status}\n\n{text}",
            parent=self.root,
        )

    def export_support(self) -> None:
        json_path, txt_path = self.controller.export_support_package()
        messagebox.showinfo(
            "Soporte",
            f"Paquete exportado:\n{json_path}\n{txt_path}",
            parent=self.root,
        )


def run_gui_app() -> None:
    app = GuiApp()
    app.run()
