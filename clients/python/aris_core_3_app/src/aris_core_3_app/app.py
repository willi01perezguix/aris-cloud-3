from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from aris3_client_sdk import ApiSession, ClientConfig, load_config
from aris3_client_sdk.clients.access_control import AccessControlClient
from aris3_client_sdk.clients.auth import AuthClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.models import PermissionEntry


@dataclass
class MenuItem:
    label: str
    permission_key: str
    enabled: bool = False


CORE_MENU = [
    MenuItem("Stock", "stock.view"),
    MenuItem("POS", "pos.view"),
    MenuItem("Transfers", "transfers.view"),
    MenuItem("Inventory Counts", "inventory.counts.view"),
    MenuItem("Reports", "reports.view"),
]


def build_menu_items(allowed_permissions: set[str]) -> list[MenuItem]:
    return [
        MenuItem(item.label, item.permission_key, item.permission_key in allowed_permissions)
        for item in CORE_MENU
    ]


def allowed_permission_set(decisions: list[PermissionEntry]) -> set[str]:
    return {entry.key for entry in decisions if entry.allowed}


class CoreAppShell:
    def __init__(self, config: ClientConfig | None = None, session: ApiSession | None = None) -> None:
        self.config = config or load_config()
        self.session = session or ApiSession(self.config)
        self.root: tk.Tk | None = None
        self.status_var = tk.StringVar(value="Disconnected")
        self.menu_buttons: list[ttk.Button] = []
        self.error_var = tk.StringVar(value="")

    def start(self, headless: bool = False) -> None:
        if headless:
            return
        self.root = tk.Tk()
        self.root.title("ARIS CORE 3")
        self._build_login_ui()
        self.root.mainloop()

    def _build_login_ui(self) -> None:
        if self.root is None:
            return
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="ARIS CORE 3 Login").grid(row=0, column=0, columnspan=2, pady=(0, 12))

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

        allowed = allowed_permission_set(permissions.permissions)
        self._show_main_ui(user.username, user.role or "")
        self._apply_menu_state(build_menu_items(allowed))

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
        menu_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.menu_buttons = []
        for item in CORE_MENU:
            button = ttk.Button(menu_frame, text=item.label, state=tk.DISABLED)
            button.pack(fill="x", pady=2)
            self.menu_buttons.append(button)

    def _apply_menu_state(self, menu_items: list[MenuItem]) -> None:
        for button, item in zip(self.menu_buttons, menu_items):
            button.configure(state=tk.NORMAL if item.enabled else tk.DISABLED)


def main() -> None:
    app = CoreAppShell()
    app.start()


if __name__ == "__main__":
    main()
