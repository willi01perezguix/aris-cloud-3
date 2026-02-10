from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from aris3_client_sdk import ApiSession, ClientConfig, load_config
from aris3_client_sdk.clients.access_control import AccessControlClient
from aris3_client_sdk.clients.auth import AuthClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.models import EffectivePermissionsResponse, PermissionEntry


@dataclass
class MenuItem:
    label: str
    permission_key: str
    enabled: bool = False


CONTROL_CENTER_MENU = [
    MenuItem("Tenants", "tenants.view"),
    MenuItem("Stores", "stores.view"),
    MenuItem("Users", "users.view"),
    MenuItem("RBAC", "rbac.view"),
    MenuItem("Settings", "settings.view"),
    MenuItem("Audit", "audit.view"),
    MenuItem("Permissions Inspector", "rbac.view"),
]


def build_menu_items(allowed_permissions: set[str]) -> list[MenuItem]:
    return [
        MenuItem(item.label, item.permission_key, item.permission_key in allowed_permissions)
        for item in CONTROL_CENTER_MENU
    ]


def allowed_permission_set(decisions: list[PermissionEntry]) -> set[str]:
    return {entry.key for entry in decisions if entry.allowed}


def group_permissions(entries: list[PermissionEntry]) -> dict[str, list[PermissionEntry]]:
    grouped: dict[str, list[PermissionEntry]] = {}
    for entry in sorted(entries, key=lambda x: x.key):
        module = entry.key.split(".")[0] if "." in entry.key else entry.key.split("_")[0].lower()
        grouped.setdefault(module, []).append(entry)
    return grouped


def _ensure_default_root() -> None:
    if tk._default_root is not None:
        return
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        root = tk.Tcl()
    tk._default_root = root


class ControlCenterAppShell:
    def __init__(self, config: ClientConfig | None = None, session: ApiSession | None = None) -> None:
        _ensure_default_root()
        self.config = config or load_config()
        self.session = session or ApiSession(self.config)
        self.root: tk.Tk | None = tk._default_root if isinstance(tk._default_root, tk.Tk) else None
        self.menu_buttons: list[ttk.Button] = []
        self.error_var = tk.StringVar(value="")
        self.allowed_permissions: set[str] = set()
        self.content_frame: ttk.Frame | None = None
        self.inspector_user_id_var = tk.StringVar(value="")
        self.inspector_error_var = tk.StringVar(value="")
        self.inspector_trace_var = tk.StringVar(value="")
        self.inspector_matrix_var = tk.StringVar(value="")

    def start(self, headless: bool = False) -> None:
        if headless:
            return
        if self.root is None:
            self.root = tk.Tk()
        else:
            self.root.deiconify()
        self.root.title("ARIS Control Center")
        self._build_login_ui()
        self.root.mainloop()

    def _build_login_ui(self) -> None:
        if self.root is None:
            return
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="ARIS Control Center Login").grid(row=0, column=0, columnspan=2, pady=(0, 12))

        ttk.Label(frame, text="Username or Email").grid(row=1, column=0, sticky="w")
        username_entry = ttk.Entry(frame, width=30)
        username_entry.grid(row=1, column=1, sticky="ew")

        ttk.Label(frame, text="Password").grid(row=2, column=0, sticky="w")
        password_entry = ttk.Entry(frame, width=30, show="*")
        password_entry.grid(row=2, column=1, sticky="ew")

        login_button = ttk.Button(
            frame,
            text="Login",
            command=lambda: self._login(username_entry.get(), password_entry.get()),
        )
        login_button.grid(row=3, column=0, columnspan=2, pady=(10, 0))

        ttk.Label(frame, textvariable=self.error_var, foreground="red").grid(row=4, column=0, columnspan=2, pady=(8, 0))

        frame.columnconfigure(1, weight=1)

    def _login(self, username: str, password: str) -> None:
        self.error_var.set("")
        try:
            auth_client = AuthClient(http=self.session._http())
            token = auth_client.login(username, password)
            session_auth = AuthClient(http=self.session._http(), access_token=token.access_token)
            user = session_auth.me()
            access_client = AccessControlClient(http=self.session._http(), access_token=token.access_token)
            permissions = access_client.effective_permissions()
            self.session.establish(token, user)
        except ApiError as exc:
            self.error_var.set(str(exc))
            return

        self.allowed_permissions = allowed_permission_set(permissions.permissions)
        self.inspector_user_id_var.set(user.id)
        self._show_main_ui(user.username, user.role or "")
        self._apply_menu_state(build_menu_items(self.allowed_permissions))

    def _show_main_ui(self, username: str, role: str) -> None:
        if self.root is None:
            return
        for child in self.root.winfo_children():
            child.destroy()
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        status_text = f"Connected: {username} ({role}) [env: {self.config.env_name}]"
        ttk.Label(frame, text=status_text).pack(anchor="w")

        menu_frame = ttk.LabelFrame(frame, text="Main Menu", padding=10)
        menu_frame.pack(fill="x", pady=(10, 0))
        self.content_frame = ttk.Frame(frame)
        self.content_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.menu_buttons = []
        for item in CONTROL_CENTER_MENU:
            command = self._show_permissions_inspector if item.label == "Permissions Inspector" else (lambda label=item.label: self._show_placeholder(label))
            button = ttk.Button(menu_frame, text=item.label, state=tk.DISABLED, command=command)
            button.pack(fill="x", pady=2)
            self.menu_buttons.append(button)
        self._show_placeholder("Select a menu option.")

    def _apply_menu_state(self, menu_items: list[MenuItem]) -> None:
        for button, item in zip(self.menu_buttons, menu_items):
            button.configure(state=tk.NORMAL if item.enabled else tk.DISABLED)

    def _show_placeholder(self, message: str) -> None:
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()
        ttk.Label(self.content_frame, text=message, foreground="gray").pack(anchor="w")

    def _show_permissions_inspector(self) -> None:
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()

        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="Effective Permissions Inspector", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        if "rbac.view" not in self.allowed_permissions:
            ttk.Label(container, text="No RBAC view permission.", foreground="gray").pack(anchor="w", pady=(8, 0))
            return

        row = ttk.Frame(container)
        row.pack(fill="x", pady=(8, 4))
        ttk.Label(row, text="User ID").pack(side="left")
        ttk.Entry(row, textvariable=self.inspector_user_id_var, width=40).pack(side="left", padx=(8, 8))
        ttk.Button(row, text="Load", command=self._load_permissions_inspector).pack(side="left")
        ttk.Label(container, text="DENY overrides highlighted with !", foreground="gray").pack(anchor="w")
        ttk.Label(container, textvariable=self.inspector_error_var, foreground="red").pack(anchor="w")
        ttk.Label(container, textvariable=self.inspector_trace_var, foreground="gray").pack(anchor="w")
        ttk.Label(container, textvariable=self.inspector_matrix_var, justify="left").pack(anchor="w", pady=(8, 0))

    def _load_permissions_inspector(self) -> None:
        user_id = self.inspector_user_id_var.get().strip()
        self.inspector_error_var.set("")
        self.inspector_trace_var.set("")
        try:
            client = AccessControlClient(http=self.session._http(), access_token=self.session.token)
            payload = client.effective_permissions_for_user(user_id) if user_id else client.effective_permissions()
            self._render_permission_matrix(payload)
        except ApiError as exc:
            self.inspector_error_var.set(exc.message)
            self.inspector_trace_var.set(f"trace_id: {exc.trace_id}" if exc.trace_id else "")

    def _render_permission_matrix(self, payload: EffectivePermissionsResponse) -> None:
        grouped = group_permissions(payload.permissions)
        lines: list[str] = []
        denies = set(payload.denies_applied)
        for module, entries in grouped.items():
            lines.append(f"[{module}]")
            for entry in entries:
                deny_marker = " !DENY" if entry.key in denies else ""
                decision = "ALLOW" if entry.allowed else "DENY"
                lines.append(f"  - {entry.key}: {decision}{deny_marker}")
        self.inspector_matrix_var.set("\n".join(lines) if lines else "No permissions returned")
        self.inspector_trace_var.set(f"trace_id: {payload.trace_id}" if payload.trace_id else "")


def main() -> None:
    app = ControlCenterAppShell()
    app.start()


if __name__ == "__main__":
    main()
