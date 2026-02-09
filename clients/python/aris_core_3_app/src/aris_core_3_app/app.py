from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk

from aris3_client_sdk import ApiSession, ClientConfig, load_config
from aris3_client_sdk.clients.access_control import AccessControlClient
from aris3_client_sdk.clients.auth import AuthClient
from aris3_client_sdk.clients.stock_client import StockClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.models import PermissionEntry
from aris3_client_sdk.models_stock import StockQuery, StockTableResponse


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


@dataclass
class StockViewState:
    page: int = 1
    page_size: int = 50
    sort_by: str = "created_at"
    sort_dir: str = "desc"
    total_rows: int = 0
    rows: list[dict] = field(default_factory=list)
    totals: dict[str, int | None] = field(default_factory=dict)


def _default_int_env(key: str, fallback: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


def build_stock_query(
    filters: dict[str, str | None],
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
) -> StockQuery:
    return StockQuery(
        q=filters.get("q"),
        description=filters.get("description"),
        var1_value=filters.get("var1_value"),
        var2_value=filters.get("var2_value"),
        sku=filters.get("sku"),
        epc=filters.get("epc"),
        location_code=filters.get("location_code"),
        pool=filters.get("pool"),
        from_date=filters.get("from"),
        to_date=filters.get("to"),
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


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
        self.allowed_permissions: set[str] = set()
        self.content_frame: ttk.Frame | None = None
        self.stock_state = StockViewState(
            page=1,
            page_size=_default_int_env("ARIS3_DEFAULT_PAGE_SIZE", 50),
            sort_by=os.getenv("ARIS3_DEFAULT_SORT_BY", "created_at"),
            sort_dir=os.getenv("ARIS3_DEFAULT_SORT_ORDER", "desc"),
        )
        self.stock_filter_vars: dict[str, tk.StringVar] = {}
        self.stock_meta_var = tk.StringVar(value="")
        self.stock_totals_var = tk.StringVar(value="")
        self.stock_error_var = tk.StringVar(value="")
        self.stock_loading_var = tk.StringVar(value="")
        self.stock_table: ttk.Treeview | None = None
        self.stock_detail_text: tk.Text | None = None
        self.stock_page_var = tk.StringVar(value=str(self.stock_state.page))
        self.stock_page_size_var = tk.StringVar(value=str(self.stock_state.page_size))
        self.stock_sort_by_var = tk.StringVar(value=self.stock_state.sort_by)
        self.stock_sort_dir_var = tk.StringVar(value=self.stock_state.sort_dir)
        self.stock_controls: list[tk.Widget] = []

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
        self.allowed_permissions = allowed
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
        ttk.Label(frame, text=status_text).grid(row=0, column=0, columnspan=2, sticky="w")

        menu_frame = ttk.LabelFrame(frame, text="Main Menu", padding=10)
        menu_frame.grid(row=1, column=0, sticky="ns", padx=(0, 12), pady=(10, 0))

        self.content_frame = ttk.Frame(frame)
        self.content_frame.grid(row=1, column=1, sticky="nsew", pady=(10, 0))

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(1, weight=1)

        self.menu_buttons = []
        for item in CORE_MENU:
            if item.label == "Stock":
                command = self._show_stock_view
            else:
                command = lambda label=item.label: self._show_placeholder(label)
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
        placeholder = ttk.Frame(self.content_frame, padding=20)
        placeholder.pack(fill="both", expand=True)
        ttk.Label(placeholder, text=message).pack(anchor="center")

    def _is_stock_allowed(self) -> bool:
        return "stock.view" in self.allowed_permissions

    def _ensure_stock_filter_vars(self) -> None:
        if self.stock_filter_vars:
            return
        keys = [
            "q",
            "sku",
            "epc",
            "description",
            "var1_value",
            "var2_value",
            "location_code",
            "pool",
            "from",
            "to",
        ]
        self.stock_filter_vars = {key: tk.StringVar(value="") for key in keys}

    def _collect_stock_filters(self) -> dict[str, str | None]:
        self._ensure_stock_filter_vars()
        filters: dict[str, str | None] = {}
        for key, var in self.stock_filter_vars.items():
            value = var.get().strip()
            filters[key] = value if value else None
        return filters

    def _clear_stock_filters(self) -> None:
        self._ensure_stock_filter_vars()
        for var in self.stock_filter_vars.values():
            var.set("")

    def _show_stock_view(self) -> None:
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()

        self._ensure_stock_filter_vars()
        allowed = self._is_stock_allowed()
        state = tk.NORMAL if allowed else tk.DISABLED

        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, padding=(0, 0, 0, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Stock", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        if not allowed:
            ttk.Label(
                header,
                text="You do not have permission to view stock data.",
                foreground="red",
            ).pack(anchor="w", pady=(4, 0))

        summary = ttk.Frame(container)
        summary.pack(fill="x", pady=(4, 8))
        ttk.Label(summary, textvariable=self.stock_meta_var).pack(anchor="w")
        ttk.Label(summary, textvariable=self.stock_totals_var).pack(anchor="w")
        ttk.Label(summary, textvariable=self.stock_loading_var, foreground="blue").pack(anchor="w")
        ttk.Label(summary, textvariable=self.stock_error_var, foreground="red").pack(anchor="w")

        filter_frame = ttk.LabelFrame(container, text="Filters", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))

        fields = [
            ("q", "Query"),
            ("sku", "SKU"),
            ("epc", "EPC"),
            ("description", "Description"),
            ("var1_value", "Var1 Value"),
            ("var2_value", "Var2 Value"),
            ("location_code", "Location Code"),
            ("pool", "Pool"),
            ("from", "From"),
            ("to", "To"),
        ]
        for idx, (key, label) in enumerate(fields):
            row = idx // 2
            col = (idx % 2) * 2
            ttk.Label(filter_frame, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=2)
            entry = ttk.Entry(filter_frame, textvariable=self.stock_filter_vars[key], width=28, state=state)
            entry.grid(row=row, column=col + 1, sticky="ew", pady=2)

        filter_frame.columnconfigure(1, weight=1)
        filter_frame.columnconfigure(3, weight=1)

        controls = ttk.Frame(filter_frame)
        controls.grid(row=5, column=0, columnspan=4, sticky="w", pady=(6, 0))
        search_button = ttk.Button(
            controls,
            text="Search",
            command=lambda: self._fetch_stock(reset_page=True),
            state=state,
        )
        clear_button = ttk.Button(controls, text="Clear", command=self._clear_stock_filters, state=state)
        refresh_button = ttk.Button(
            controls,
            text="Refresh current page",
            command=lambda: self._fetch_stock(reset_page=False),
            state=state,
        )
        search_button.pack(side="left", padx=(0, 6))
        clear_button.pack(side="left", padx=(0, 6))
        refresh_button.pack(side="left")

        pagination = ttk.Frame(container)
        pagination.pack(fill="x", pady=(0, 8))
        prev_button = ttk.Button(
            pagination,
            text="Prev",
            command=self._prev_stock_page,
            state=state,
        )
        next_button = ttk.Button(
            pagination,
            text="Next",
            command=self._next_stock_page,
            state=state,
        )
        ttk.Label(pagination, text="Page").pack(side="left", padx=(0, 4))
        ttk.Label(pagination, textvariable=self.stock_page_var).pack(side="left", padx=(0, 12))
        ttk.Label(pagination, text="Page size").pack(side="left", padx=(0, 4))
        page_size_select = ttk.Combobox(
            pagination,
            textvariable=self.stock_page_size_var,
            values=("25", "50", "100"),
            width=6,
            state="readonly" if allowed else "disabled",
        )
        page_size_select.bind("<<ComboboxSelected>>", lambda _evt: self._on_page_size_change())
        prev_button.pack(side="left", padx=(0, 6))
        next_button.pack(side="left", padx=(0, 12))
        page_size_select.pack(side="left")

        table_frame = ttk.Frame(container)
        table_frame.pack(fill="both", expand=True)
        columns = (
            "sku",
            "epc",
            "description",
            "location_code",
            "pool",
            "status",
            "updated_at",
        )
        self.stock_table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=10,
        )
        for col in columns:
            self.stock_table.heading(col, text=col.replace("_", " ").title())
            self.stock_table.column(col, width=140, anchor="w")
        self.stock_table.bind("<<TreeviewSelect>>", self._on_stock_row_selected)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.stock_table.yview)
        self.stock_table.configure(yscrollcommand=scrollbar.set)
        self.stock_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        detail_frame = ttk.LabelFrame(container, text="Row Details", padding=6)
        detail_frame.pack(fill="both", expand=True, pady=(8, 0))
        self.stock_detail_text = tk.Text(detail_frame, height=8, wrap="none")
        self.stock_detail_text.pack(fill="both", expand=True)

        self.stock_controls = [
            search_button,
            clear_button,
            refresh_button,
            prev_button,
            next_button,
            page_size_select,
        ]
        if not allowed:
            self._set_stock_controls_state(tk.DISABLED)

    def _set_stock_controls_state(self, state: str) -> None:
        for widget in self.stock_controls:
            widget.configure(state=state)

    def _on_page_size_change(self) -> None:
        try:
            self.stock_state.page_size = int(self.stock_page_size_var.get())
        except ValueError:
            return
        self.stock_state.page = 1
        self.stock_page_var.set(str(self.stock_state.page))
        self._fetch_stock(reset_page=True)

    def _prev_stock_page(self) -> None:
        if self.stock_state.page > 1:
            self.stock_state.page -= 1
            self.stock_page_var.set(str(self.stock_state.page))
            self._fetch_stock(reset_page=False)

    def _next_stock_page(self) -> None:
        if self.stock_state.total_rows and self.stock_state.page_size:
            max_page = max(1, (self.stock_state.total_rows + self.stock_state.page_size - 1) // self.stock_state.page_size)
            if self.stock_state.page >= max_page:
                return
        self.stock_state.page += 1
        self.stock_page_var.set(str(self.stock_state.page))
        self._fetch_stock(reset_page=False)

    def _fetch_stock(self, reset_page: bool = False) -> None:
        if not self._is_stock_allowed():
            return
        if reset_page:
            self.stock_state.page = 1
            self.stock_page_var.set(str(self.stock_state.page))
        self.stock_error_var.set("")
        self.stock_loading_var.set("Loading stock...")
        self._set_stock_controls_state(tk.DISABLED)
        query = build_stock_query(
            self._collect_stock_filters(),
            page=self.stock_state.page,
            page_size=self.stock_state.page_size,
            sort_by=self.stock_sort_by_var.get(),
            sort_order=self.stock_sort_dir_var.get(),
        )

        def worker() -> None:
            try:
                response = self._request_stock(query)
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._handle_stock_error(exc))
                return
            if self.root:
                self.root.after(0, lambda: self._update_stock_results(response))

        threading.Thread(target=worker, daemon=True).start()

    def _request_stock(self, query: StockQuery, client: StockClient | None = None) -> StockTableResponse:
        api_client = client or StockClient(http=self.session._http(), access_token=self.session.token)
        return api_client.get_stock(query)

    def _handle_stock_error(self, exc: ApiError) -> None:
        self.stock_loading_var.set("")
        self.stock_error_var.set(str(exc))
        self._set_stock_controls_state(tk.NORMAL)

    def _update_stock_results(self, response: StockTableResponse) -> None:
        self.stock_loading_var.set("")
        self._set_stock_controls_state(tk.NORMAL)
        self.stock_state.total_rows = response.totals.total_rows or 0
        self.stock_state.rows = [row.model_dump(mode="json") for row in response.rows]
        self.stock_state.totals = response.totals.model_dump(mode="json")
        self.stock_meta_var.set(
            f"Rows: {response.totals.total_rows} | Page {response.meta.page} of size {response.meta.page_size}"
        )
        self.stock_totals_var.set(
            "Totals: "
            f"RFID={response.totals.total_rfid} "
            f"Pending={response.totals.total_pending} "
            f"Units={response.totals.total_units}"
        )
        self._populate_stock_table()

    def _populate_stock_table(self) -> None:
        if self.stock_table is None:
            return
        for item in self.stock_table.get_children():
            self.stock_table.delete(item)
        for idx, row in enumerate(self.stock_state.rows):
            values = (
                row.get("sku"),
                row.get("epc"),
                row.get("description"),
                row.get("location_code"),
                row.get("pool"),
                row.get("status"),
                row.get("updated_at"),
            )
            self.stock_table.insert("", "end", iid=str(idx), values=values)

    def _on_stock_row_selected(self, _event: tk.Event) -> None:
        if self.stock_table is None or self.stock_detail_text is None:
            return
        selected = self.stock_table.selection()
        if not selected:
            return
        idx = int(selected[0])
        if idx >= len(self.stock_state.rows):
            return
        payload = self.stock_state.rows[idx]
        pretty = json.dumps(payload, indent=2, default=str)
        self.stock_detail_text.delete("1.0", tk.END)
        self.stock_detail_text.insert(tk.END, pretty)


def main() -> None:
    app = CoreAppShell()
    app.start()


if __name__ == "__main__":
    main()
