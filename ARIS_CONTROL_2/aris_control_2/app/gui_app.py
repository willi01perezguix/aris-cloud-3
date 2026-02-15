from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from aris_control_2.app.gui_controller import GuiController, LoginResult
from aris_control_2.app.gui_views import LoginDialog, MainWindow


MODULE_PERMISSIONS: dict[str, set[str]] = {
    "tenants": {"tenants.view", "tenants.read", "admin.read"},
    "stores": {"stores.view", "stores.read", "admin.read"},
    "users": {"users.view", "users.read", "admin.read"},
    "stock": {"stock.view", "stock.read", "inventory.view", "admin.read"},
    "transfers": {"transfers.view", "transfers.read", "admin.read"},
    "pos": {"pos.view", "pos.read", "admin.read"},
    "reports": {"reports.view", "reports.read", "admin.read"},
}
OPERATIONAL_MODULES = {"stores", "users", "stock", "transfers", "pos", "reports"}


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
        if hasattr(self.window, "set_module_open_handler"):
            self.window.set_module_open_handler(self.open_module)
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
            self._sync_module_launcher_state()
            self.window.show_authenticated_view()
            self._authenticated_view_active = True
        finally:
            self._navigating_authenticated = False

    def _sync_module_launcher_state(self) -> None:
        if not hasattr(self.window, "set_module_launcher_state"):
            return

        session = self.controller.session
        role = (session.role or "").upper()
        has_tenant = bool(session.effective_tenant_id)
        enabled_by_module = self._modules_enabled_by_scope()
        notice = ""

        if role == "SUPERADMIN" and not has_tenant:
            notice = "Selecciona tenant para habilitar módulos operativos."
            for module in OPERATIONAL_MODULES:
                enabled_by_module[module] = False
            enabled_by_module["tenants"] = True

        self.window.set_module_launcher_state(enabled_by_module=enabled_by_module, notice=notice)

    def _modules_enabled_by_scope(self) -> dict[str, bool]:
        session = self.controller.session
        permissions = self._effective_permissions(session.user)
        enabled: dict[str, bool] = {}

        for module, required_scopes in MODULE_PERMISSIONS.items():
            if permissions:
                enabled[module] = bool(required_scopes.intersection(permissions))
            else:
                enabled[module] = bool(session.role)
        return enabled

    @staticmethod
    def _effective_permissions(user_payload: dict[str, object] | None) -> set[str]:
        if not isinstance(user_payload, dict):
            return set()

        for key in ("effective_permissions", "permissions", "scopes"):
            values = user_payload.get(key)
            if isinstance(values, list):
                return {str(item) for item in values}
        return set()

    def open_module(self, module: str) -> None:
        self.controller.session.current_module = module
        self.controller.support_center.record_operation(
            module=module,
            screen="launcher",
            action="open",
            result="success",
            latency_ms=0,
            code="OK",
            message=f"module {module} open",
        )
        self._refresh_header()
        if self._authenticated_view_active:
            self._navigate_to_authenticated_view_refresh()

    def _navigate_to_authenticated_view_refresh(self) -> None:
        session = self.controller.session
        user_payload = session.user or {}
        username = str(user_payload.get("username") or user_payload.get("email") or "-")
        role = session.role or "-"
        tenant_id = session.effective_tenant_id or "-"
        self.window.set_session_context(user=username, role=role, effective_tenant_id=tenant_id)
        self._sync_module_launcher_state()
        self.window.show_authenticated_view()

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
