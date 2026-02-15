from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from aris_control_2.app.gui_controller import GuiController, LoginResult
from aris_control_2.app.gui_views import LoginDialog, MainWindow


class GuiApp:
    def __init__(
        self,
        controller: GuiController | None = None,
        *,
        window_cls: type[MainWindow] = MainWindow,
        login_dialog_cls: type[LoginDialog] = LoginDialog,
    ) -> None:
        self.controller = controller or GuiController()
        self._login_dialog_cls = login_dialog_cls
        self._navigating_authenticated = False
        self._authenticated_view_active = False
        self.root = tk.Tk()
        self.window = window_cls(
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
        dialog = self._login_dialog_cls(self.root, self._submit_login)
        dialog.wait()
        self._refresh_header()

    def _submit_login(self, username_or_email: str, password: str) -> LoginResult:
        result = self.controller.login(username_or_email=username_or_email, password=password)
        if result.success:
            self._navigate_to_authenticated_view()
        return result

    def _navigate_to_authenticated_view(self) -> None:
        if self._navigating_authenticated or self._authenticated_view_active:
            return
        self._navigating_authenticated = True
        try:
            session = self.controller.session
            user_payload = session.user or {}
            username = str(user_payload.get("username") or user_payload.get("email") or "-")
            role = session.role or "-"
            tenant_id = session.effective_tenant_id or "-"

            self.window.set_session_context(user=username, role=role, effective_tenant_id=tenant_id)
            self.window.show_authenticated_view()
            self._authenticated_view_active = True
        finally:
            self._navigating_authenticated = False

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
