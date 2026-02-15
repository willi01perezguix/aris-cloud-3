from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from aris3_client_sdk import ApiSession, ClientConfig, load_config
from aris3_client_sdk.clients.access_control import AccessControlClient
from aris3_client_sdk.clients.auth import AuthClient
from aris3_client_sdk.clients.reports_client import ReportsClient
from aris3_client_sdk.clients.media_client import MediaClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.models import EffectivePermissionsResponse, PermissionEntry


@dataclass
class MenuItem:
    label: str
    permission_keys: tuple[str, ...]
    enabled: bool = False


CONTROL_CENTER_MENU = [
    MenuItem("Tenants", ("tenants.view", "TENANTS_VIEW")),
    MenuItem("Stores", ("stores.view", "STORES_VIEW", "STORE_VIEW")),
    MenuItem("Users", ("users.view", "USERS_VIEW")),
    MenuItem("Stock", ("stock.view", "STOCK_VIEW")),
    MenuItem("Transfers", ("transfers.view", "TRANSFERS_VIEW")),
    MenuItem("POS", ("pos.view", "pos_sales.view", "POS_VIEW", "POS_SALES_VIEW")),
    MenuItem("Reports", ("reports.view", "REPORTS_VIEW")),
]


def build_menu_items(allowed_permissions: set[str]) -> list[MenuItem]:
    return [
        MenuItem(
            item.label,
            item.permission_keys,
            any(permission in allowed_permissions for permission in item.permission_keys),
        )
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
        self.insights_status_var = tk.StringVar(value="")
        self.insights_kpi_var = tk.StringVar(value="")
        self.insights_trace_var = tk.StringVar(value="")
        self.media_sku_var = tk.StringVar(value="")
        self.media_var1_var = tk.StringVar(value="")
        self.media_var2_var = tk.StringVar(value="")
        self.media_result_var = tk.StringVar(value="")
        self.media_trace_var = tk.StringVar(value="")
        self.current_screen = "login"
        self.active_module = ""

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

    def _clear_root(self) -> None:
        if self.root is None:
            return
        for child in self.root.winfo_children():
            child.destroy()

    def _build_login_ui(self) -> None:
        if self.root is None:
            return
        self.current_screen = "login"
        self.active_module = ""
        self._clear_root()
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
        self._show_main_ui()
        self._apply_menu_state(build_menu_items(self.allowed_permissions))

    def _show_main_ui(self) -> None:
        if self.root is None:
            return
        self.current_screen = "authenticated"
        self._clear_root()
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill="both", expand=True)

        session_user = self.session.user
        username = session_user.username if session_user else "-"
        role = session_user.role if session_user and session_user.role else "-"
        tenant = session_user.tenant_id if session_user and session_user.tenant_id else "-"
        connectivity = "Online" if self.session.token else "Offline"
        status_text = f"Usuario: {username} | Rol: {role} | Tenant efectivo: {tenant} | Conectividad: {connectivity}"
        ttk.Label(frame, text=status_text).pack(anchor="w")

        menu_frame = ttk.LabelFrame(frame, text="Módulos", padding=10)
        menu_frame.pack(fill="x", pady=(10, 0))
        self.content_frame = ttk.Frame(frame)
        self.content_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.menu_buttons = []
        for item in CONTROL_CENTER_MENU:
            command = lambda label=item.label: self._open_module(label)
            button = ttk.Button(menu_frame, text=item.label, state=tk.DISABLED, command=command)
            button.pack(fill="x", pady=2)
            self.menu_buttons.append(button)

        logout_button = ttk.Button(menu_frame, text="Logout", command=self._logout)
        logout_button.pack(fill="x", pady=(8, 2))
        self.menu_buttons.append(logout_button)
        self._show_placeholder("Selecciona un módulo.")

    def _apply_menu_state(self, menu_items: list[MenuItem]) -> None:
        for button, item in zip(self.menu_buttons, menu_items):
            button.configure(state=tk.NORMAL if item.enabled else tk.DISABLED)
        if self.menu_buttons:
            self.menu_buttons[-1].configure(state=tk.NORMAL)

    def _open_module(self, module_label: str) -> None:
        self.active_module = module_label
        self.current_screen = "module"
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()
        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text=module_label, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        ttk.Label(container, text=f"Vista placeholder de {module_label}.", foreground="gray").pack(anchor="w", pady=(8, 0))
        ttk.Button(container, text="Volver", command=self._return_to_shell).pack(anchor="w", pady=(12, 0))

    def _return_to_shell(self) -> None:
        self.current_screen = "authenticated"
        self.active_module = ""
        self._show_placeholder("Selecciona un módulo.")

    def _logout(self) -> None:
        self.session.logout()
        self.allowed_permissions = set()
        self._build_login_ui()

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


    def _show_operational_insights(self) -> None:
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()

        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="Operational Insights", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        if "reports.view" not in self.allowed_permissions and "REPORTS_VIEW" not in self.allowed_permissions:
            ttk.Label(container, text="No report visibility permission.", foreground="gray").pack(anchor="w", pady=(8, 0))
            return
        row = ttk.Frame(container)
        row.pack(fill="x", pady=(8, 6))
        ttk.Button(row, text="Refresh", command=self._load_operational_insights).pack(side="left")
        ttk.Label(container, textvariable=self.insights_status_var, foreground="gray").pack(anchor="w")
        ttk.Label(container, textvariable=self.insights_kpi_var, justify="left").pack(anchor="w", pady=(6, 0))
        ttk.Label(container, textvariable=self.insights_trace_var, foreground="gray").pack(anchor="w")

    def _load_operational_insights(self) -> None:
        self.insights_status_var.set("Loading…")
        self.insights_trace_var.set("")
        try:
            client = ReportsClient(http=self.session._http(), access_token=self.session.token)
            payload = client.get_sales_overview()
            totals = payload.totals
            self.insights_kpi_var.set(
                f"store={payload.meta.store_id}\nnet={totals.net_sales} gross={totals.gross_sales} orders={totals.orders_paid_count} avg={totals.average_ticket}"
            )
            self.insights_status_var.set(f"Last update: {payload.meta.to_datetime.isoformat()}")
            self.insights_trace_var.set(f"trace_id: {payload.meta.trace_id}" if payload.meta.trace_id else "")
        except ApiError as exc:
            self.insights_status_var.set("Failed to load insights")
            self.insights_kpi_var.set(exc.message)
            self.insights_trace_var.set(f"trace_id: {exc.trace_id}" if exc.trace_id else "")


    def _show_media_inspector(self) -> None:
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()
        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="Media Inspector", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        if "stock.view" not in self.allowed_permissions and "STORE_VIEW" not in self.allowed_permissions:
            ttk.Label(container, text="No media read permission.", foreground="gray").pack(anchor="w", pady=(8, 0))
            return
        form = ttk.Frame(container)
        form.pack(anchor="w", pady=(8, 6))
        ttk.Label(form, text="SKU").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.media_sku_var, width=20).grid(row=0, column=1, padx=(8, 8))
        ttk.Label(form, text="Var1").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.media_var1_var, width=14).grid(row=0, column=3, padx=(8, 8))
        ttk.Label(form, text="Var2").grid(row=0, column=4, sticky="w")
        ttk.Entry(form, textvariable=self.media_var2_var, width=14).grid(row=0, column=5, padx=(8, 8))
        ttk.Button(form, text="Resolve", command=self._load_media_resolution).grid(row=0, column=6)
        ttk.Label(container, textvariable=self.media_result_var, justify="left").pack(anchor="w", pady=(6, 0))
        ttk.Label(container, textvariable=self.media_trace_var, foreground="gray").pack(anchor="w")

    def _load_media_resolution(self) -> None:
        sku = self.media_sku_var.get().strip()
        self.media_trace_var.set("")
        if not sku:
            self.media_result_var.set("sku is required")
            return
        try:
            client = MediaClient(http=self.session._http(), access_token=self.session.token)
            payload = client.resolve_for_variant(
                sku,
                self.media_var1_var.get().strip() or None,
                self.media_var2_var.get().strip() or None,
            )
            self.media_result_var.set(
                "source={source}\nimage_url={image_url}\nthumb_url={thumb_url}\nasset_id={asset_id}".format(
                    source=payload.source,
                    image_url=payload.resolved.url,
                    thumb_url=payload.resolved.thumb_url,
                    asset_id=payload.resolved.asset_id,
                )
            )
            self.media_trace_var.set(f"trace_id: {payload.trace_id}" if payload.trace_id else "")
        except ApiError as exc:
            self.media_result_var.set(f"{exc.code}: {exc.message}")
            self.media_trace_var.set(f"trace_id: {exc.trace_id}" if exc.trace_id else "")


def main() -> None:
    app = ControlCenterAppShell()
    app.start()


if __name__ == "__main__":
    main()
