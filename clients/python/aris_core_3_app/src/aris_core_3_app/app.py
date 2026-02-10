from __future__ import annotations

import csv
import json
import os
import threading
import tkinter as tk
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from tkinter import filedialog, messagebox, ttk

from aris3_client_sdk import ApiSession, ClientConfig, load_config, new_idempotency_keys, to_user_facing_error
from aris3_client_sdk.clients.access_control import AccessControlClient
from aris3_client_sdk.clients.auth import AuthClient
from aris3_client_sdk.clients.pos_cash_client import PosCashClient
from aris3_client_sdk.clients.inventory_counts_client import InventoryCountsClient
from aris3_client_sdk.clients.reports_client import ReportsClient
from aris3_client_sdk.clients.exports_client import ExportsClient
from aris3_client_sdk.clients.pos_sales_client import PosSalesClient
from aris3_client_sdk.clients.stock_client import StockClient
from aris3_client_sdk.clients.transfers_client import TransfersClient
from aris3_client_sdk.clients.media_client import MediaClient
from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.image_utils import ImageMemoCache, safe_image_url, placeholder_image_ref
from aris3_client_sdk.models import PermissionEntry
from aris3_client_sdk.models_pos_cash import (
    PosCashDayCloseResponse,
    PosCashMovementResponse,
    PosCashSessionSummary,
)
from aris3_client_sdk.models_pos_sales import (
    PosPaymentCreate,
    PosSaleLineCreate,
    PosSaleLineSnapshot,
    PosSaleResponse,
)
from aris3_client_sdk.models_stock import StockQuery, StockTableResponse
from aris3_client_sdk.models_inventory_counts import CountHeader, ScanBatchRequest
from aris3_client_sdk.models_transfers import TransferQuery, TransferResponse
from aris3_client_sdk.models_reports import (
    ReportCalendarResponse,
    ReportDailyResponse,
    ReportFilter,
    normalize_report_filters,
)
from aris3_client_sdk.models_exports import ExportStatus, ExportTerminalState
from aris3_client_sdk.payment_validation import PaymentValidationIssue, validate_checkout_payload
from aris3_client_sdk.pos_cash_validation import (
    CashValidationIssue,
    validate_cash_in_payload,
    validate_cash_out_payload,
    validate_close_session_payload,
    validate_day_close_payload,
    validate_open_session_payload,
)
from aris3_client_sdk.stock_validation import (
    ClientValidationError,
    ValidationIssue,
    validate_import_epc_line,
    validate_import_sku_line,
    validate_migration_line,
)
from aris3_client_sdk.transfer_state import transfer_action_availability
from aris3_client_sdk.inventory_count_state import inventory_count_action_availability
from aris3_client_sdk.inventory_counts_validation import (
    ClientValidationError as InventoryValidationError,
    validate_scan_batch_payload,
)
from aris3_client_sdk.transfer_validation import (
    validate_cancel_payload,
    validate_create_transfer_payload,
    validate_dispatch_payload,
    validate_receive_payload,
    validate_shortage_report_payload,
    validate_shortage_resolution_payload,
    validate_update_transfer_payload,
)


@dataclass
class MenuItem:
    label: str
    permission_key: str
    enabled: bool = False


CORE_MENU = [
    MenuItem("Stock", "stock.view"),
    MenuItem("POS", "POS_SALE_VIEW"),
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


@dataclass
class PosViewState:
    sale: PosSaleResponse | None = None
    lines: list[PosSaleLineCreate] = field(default_factory=list)
    busy: bool = False


@dataclass
class PosCashViewState:
    session: PosCashSessionSummary | None = None
    movements: list[PosCashMovementResponse] = field(default_factory=list)
    last_day_close: PosCashDayCloseResponse | None = None
    busy: bool = False


@dataclass
class TransferViewState:
    rows: list[TransferResponse] = field(default_factory=list)
    selected: TransferResponse | None = None
    busy: bool = False




@dataclass
class ReportsViewState:
    filter: ReportFilter = field(default_factory=ReportFilter)
    daily: ReportDailyResponse | None = None
    calendar: ReportCalendarResponse | None = None
    mode: str = "daily"
    exports: list[ExportStatus] = field(default_factory=list)
    sort_column: str = "business_date"
    sort_desc: bool = True
    auto_poll: bool = False
    busy: bool = False


@dataclass
class InventoryCountViewState:
    selected: CountHeader | None = None
    busy: bool = False


def _default_int_env(key: str, fallback: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None



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


def _ensure_default_root() -> None:
    if tk._default_root is not None:
        return
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        root = tk.Tcl()
    tk._default_root = root


class CoreAppShell:
    def __init__(self, config: ClientConfig | None = None, session: ApiSession | None = None) -> None:
        _ensure_default_root()
        self.config = config or load_config()
        self.session = session or ApiSession(self.config)
        self.root: tk.Tk | None = tk._default_root if isinstance(tk._default_root, tk.Tk) else None
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
        self.stock_action_status_var = tk.StringVar(value="")
        self.stock_action_error_var = tk.StringVar(value="")
        self.stock_action_trace_var = tk.StringVar(value="")
        self.stock_table: ttk.Treeview | None = None
        self.stock_detail_text: tk.Text | None = None
        self.stock_show_images_var = tk.BooleanVar(
            value=os.getenv("MEDIA_ENABLE_IMAGES", "true").strip().lower() in {"1", "true", "yes", "on"}
        )
        self.stock_image_cache = ImageMemoCache(ttl_seconds=_default_int_env("MEDIA_CACHE_TTL_SEC", 300))
        self.stock_page_var = tk.StringVar(value=str(self.stock_state.page))
        self.stock_page_size_var = tk.StringVar(value=str(self.stock_state.page_size))
        self.stock_sort_by_var = tk.StringVar(value=self.stock_state.sort_by)
        self.stock_sort_dir_var = tk.StringVar(value=self.stock_state.sort_dir)
        self.stock_controls: list[tk.Widget] = []
        self.stock_action_controls: list[tk.Widget] = []
        self.transfer_state = TransferViewState()
        self.transfer_filter_vars: dict[str, tk.StringVar] = {}
        self.transfer_meta_var = tk.StringVar(value="")
        self.transfer_error_var = tk.StringVar(value="")
        self.transfer_loading_var = tk.StringVar(value="")
        self.transfer_action_status_var = tk.StringVar(value="")
        self.transfer_action_error_var = tk.StringVar(value="")
        self.transfer_action_trace_var = tk.StringVar(value="")
        self.transfer_table: ttk.Treeview | None = None
        self.transfer_detail_text: tk.Text | None = None
        self.transfer_payload_text: tk.Text | None = None
        self.transfer_selected_id_var = tk.StringVar(value="")
        self.transfer_action_buttons: dict[str, ttk.Button] = {}
        self.inventory_state = InventoryCountViewState()
        self.inventory_status_var = tk.StringVar(value="")
        self.inventory_error_var = tk.StringVar(value="")
        self.inventory_trace_var = tk.StringVar(value="")
        self.inventory_count_id_var = tk.StringVar(value="")
        self.inventory_store_id_var = tk.StringVar(value=os.getenv("ARIS3_INVENTORY_DEFAULT_STORE_ID", ""))
        self.inventory_state_var = tk.StringVar(value="")
        self.inventory_scan_epc_var = tk.StringVar(value="")
        self.inventory_scan_sku_var = tk.StringVar(value="")
        self.inventory_scan_qty_var = tk.StringVar(value="1")
        self.inventory_lock_var = tk.StringVar(value="")
        self.inventory_action_buttons: dict[str, ttk.Button] = {}
        self.pos_state = PosViewState()
        self.pos_error_var = tk.StringVar(value="")
        self.pos_trace_var = tk.StringVar(value="")
        self.pos_loading_var = tk.StringVar(value="")
        self.pos_validation_var = tk.StringVar(value="")
        self.pos_sale_status_var = tk.StringVar(value="")
        self.pos_totals_var = tk.StringVar(value="")
        self.pos_cart_var = tk.StringVar(value="")
        self.pos_cash_state = PosCashViewState()
        self.pos_cash_status_var = tk.StringVar(value="")
        self.pos_cash_meta_var = tk.StringVar(value="")
        self.pos_cash_action_status_var = tk.StringVar(value="")
        self.pos_cash_loading_var = tk.StringVar(value="")
        self.pos_cash_error_var = tk.StringVar(value="")
        self.pos_cash_trace_var = tk.StringVar(value="")
        self.pos_store_id_var = tk.StringVar(value=os.getenv("ARIS3_POS_DEFAULT_STORE_ID", ""))
        self.pos_epc_var = tk.StringVar(value="")
        self.pos_sku_var = tk.StringVar(value="")
        self.pos_qty_var = tk.StringVar(value="1")
        self.pos_unit_price_var = tk.StringVar(value="0.00")
        self.pos_line_type_var = tk.StringVar(value="SKU")
        self.pos_location_code_var = tk.StringVar(value="")
        self.pos_pool_var = tk.StringVar(value="")
        self.pos_cash_amount_var = tk.StringVar(value="0.00")
        self.pos_card_amount_var = tk.StringVar(value="0.00")
        self.pos_card_auth_var = tk.StringVar(value="")
        self.pos_transfer_amount_var = tk.StringVar(value="0.00")
        self.pos_transfer_bank_var = tk.StringVar(value="")
        self.pos_transfer_voucher_var = tk.StringVar(value="")
        self.pos_currency = os.getenv("ARIS3_POS_DEFAULT_CURRENCY", "USD")
        self.pos_cart_table: ttk.Treeview | None = None
        self.pos_show_images_var = tk.BooleanVar(
            value=os.getenv("MEDIA_ENABLE_IMAGES", "true").strip().lower() in {"1", "true", "yes", "on"}
        )
        self.pos_image_preview_var = tk.StringVar(value="Image: placeholder://aris-image")
        self.pos_image_source_var = tk.StringVar(value="Source: PLACEHOLDER")
        self.pos_cash_opening_amount_var = tk.StringVar(value="0.00")
        self.pos_cash_action_amount_var = tk.StringVar(value="0.00")
        self.pos_cash_counted_cash_var = tk.StringVar(value="0.00")
        self.pos_cash_reason_var = tk.StringVar(value="")
        default_business_date = os.getenv("ARIS3_POS_DEFAULT_BUSINESS_DATE", date.today().isoformat())
        self.pos_cash_business_date_var = tk.StringVar(value=default_business_date)
        self.pos_cash_timezone_var = tk.StringVar(value=os.getenv("ARIS3_POS_DEFAULT_TIMEZONE", "UTC"))
        self.pos_cash_force_day_close_var = tk.BooleanVar(value=False)
        self.pos_cash_movements_table: ttk.Treeview | None = None
        self.reports_state = ReportsViewState()
        self.reports_error_var = tk.StringVar(value="")
        self.reports_trace_var = tk.StringVar(value="")
        self.reports_loading_var = tk.StringVar(value="")
        self.reports_kpi_var = tk.StringVar(value="")
        self.reports_filters_var = tk.StringVar(value="")
        self.reports_table_var = tk.StringVar(value="")
        self.reports_export_status_var = tk.StringVar(value="")
        self.reports_store_id_var = tk.StringVar(value=os.getenv("ARIS3_REPORTS_DEFAULT_STORE_ID", ""))
        self.reports_from_var = tk.StringVar(value=os.getenv("ARIS3_REPORTS_DEFAULT_FROM", ""))
        self.reports_to_var = tk.StringVar(value=os.getenv("ARIS3_REPORTS_DEFAULT_TO", ""))
        self.reports_timezone_var = tk.StringVar(value=os.getenv("ARIS3_REPORTS_DEFAULT_TIMEZONE", "UTC"))
        self.reports_grouping_var = tk.StringVar(value="")
        self.reports_payment_method_var = tk.StringVar(value="")
        self.reports_business_mode_var = tk.BooleanVar(value=False)
        self.reports_auto_poll_var = tk.BooleanVar(value=False)
        self.reports_format_var = tk.StringVar(value=os.getenv("ARIS3_EXPORT_DEFAULT_FORMAT", "csv"))
        self.reports_type_var = tk.StringVar(value="reports_daily")
        self.reports_table: ttk.Treeview | None = None
        self.reports_breakdown_table: ttk.Treeview | None = None
        self.reports_export_table: ttk.Treeview | None = None

    def start(self, headless: bool = False) -> None:
        if headless:
            return
        if self.root is None:
            self.root = tk.Tk()
        else:
            self.root.deiconify()
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
        if not self.pos_store_id_var.get().strip() and user.store_id:
            self.pos_store_id_var.set(user.store_id)
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
            elif item.label == "POS":
                command = self._show_pos_view
            elif item.label == "Transfers":
                command = self._show_transfers_view
            elif item.label == "Inventory Counts":
                command = self._show_inventory_counts_view
            elif item.label == "Reports":
                command = self._show_reports_view
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

    def _has_permission(self, *keys: str) -> bool:
        return any(key in self.allowed_permissions for key in keys)

    def _is_stock_allowed(self) -> bool:
        return self._has_permission("stock.view", "STORE_VIEW", "STORE_MANAGE")

    def _can_manage_stock(self) -> bool:
        return self._has_permission("STORE_MANAGE", "stock.manage", "stock.mutations")

    def _is_transfers_allowed(self) -> bool:
        return self._has_permission("TRANSFER_VIEW", "transfers.view")

    def _can_manage_transfers(self) -> bool:
        return self._has_permission("TRANSFER_MANAGE")

    def _is_manager_role(self) -> bool:
        role = (self.session.user.role if self.session.user else None) or ""
        return role in {"MANAGER", "ADMIN", "SUPERADMIN", "PLATFORM_ADMIN"}

    def _is_inventory_counts_allowed(self) -> bool:
        return self._has_permission("inventory.counts.view", "INVENTORY_COUNT_VIEW", "INVENTORY_COUNT_MANAGE")

    def _can_manage_inventory_counts(self) -> bool:
        return self._has_permission("inventory.counts.manage", "INVENTORY_COUNT_MANAGE")

    def _show_inventory_counts_view(self) -> None:
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()
        container = ttk.Frame(self.content_frame, padding=16)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="Inventory Counts", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        if not self._is_inventory_counts_allowed():
            ttk.Label(container, text="You do not have permission to access inventory counts.", foreground="gray").pack(
                anchor="w", pady=(8, 0)
            )
            return

        status = ttk.LabelFrame(container, text="Active Count", padding=10)
        status.pack(fill="x", pady=(8, 8))
        ttk.Entry(status, textvariable=self.inventory_store_id_var, width=24).grid(row=0, column=0, padx=(0, 8))
        ttk.Entry(status, textvariable=self.inventory_count_id_var, width=36).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(status, text="Start", command=lambda: self._submit_inventory_action("START")).grid(row=0, column=2)
        ttk.Button(status, text="Refresh", command=self._refresh_inventory_count).grid(row=0, column=3, padx=(8, 0))
        ttk.Label(status, textvariable=self.inventory_lock_var).grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(status, textvariable=self.inventory_status_var).grid(row=2, column=0, columnspan=4, sticky="w")
        ttk.Label(status, textvariable=self.inventory_error_var, foreground="red").grid(row=3, column=0, columnspan=4, sticky="w")
        ttk.Label(status, textvariable=self.inventory_trace_var, foreground="gray").grid(row=4, column=0, columnspan=4, sticky="w")

        actions = ttk.LabelFrame(container, text="Lifecycle", padding=10)
        actions.pack(fill="x")
        for idx, action in enumerate(["PAUSE", "RESUME", "CLOSE", "CANCEL", "RECONCILE"]):
            btn = ttk.Button(actions, text=action.title(), command=lambda a=action: self._submit_inventory_action(a))
            btn.grid(row=0, column=idx, padx=(0, 8))
            self.inventory_action_buttons[action] = btn

        scan = ttk.LabelFrame(container, text="Scan batch", padding=10)
        scan.pack(fill="x", pady=(8, 0))
        ttk.Entry(scan, textvariable=self.inventory_scan_epc_var, width=26).grid(row=0, column=0, padx=(0, 8))
        ttk.Entry(scan, textvariable=self.inventory_scan_sku_var, width=18).grid(row=0, column=1, padx=(0, 8))
        ttk.Entry(scan, textvariable=self.inventory_scan_qty_var, width=8).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(scan, text="Submit Scan", command=self._submit_inventory_scan_batch).grid(row=0, column=3)
        self._update_inventory_action_buttons()

    def _update_inventory_action_buttons(self) -> None:
        state = self.inventory_state.selected.state if self.inventory_state.selected else ""
        availability = inventory_count_action_availability(state, can_manage=self._can_manage_inventory_counts())
        mapping = {
            "PAUSE": availability.can_pause,
            "RESUME": availability.can_resume,
            "CLOSE": availability.can_close,
            "CANCEL": availability.can_cancel,
            "RECONCILE": availability.can_reconcile,
        }
        for action, button in self.inventory_action_buttons.items():
            button.configure(state=tk.NORMAL if mapping.get(action, False) else tk.DISABLED)

    def _refresh_inventory_count(self) -> None:
        count_id = self.inventory_count_id_var.get().strip()
        if not count_id:
            return
        try:
            client = InventoryCountsClient(http=self.session._http(), access_token=self.session.token)
            response = client.get_count(count_id)
            self.inventory_state.selected = response
            self.inventory_state_var.set(response.state)
            self.inventory_lock_var.set("Store lock active" if response.lock_active else "Store lock inactive")
            self.inventory_status_var.set(f"Count {response.id} state={response.state}")
            self.inventory_error_var.set("")
            self.inventory_trace_var.set("")
        except ApiError as exc:
            self.inventory_error_var.set(exc.message)
            self.inventory_trace_var.set(f"trace_id: {exc.trace_id}" if exc.trace_id else "")
        self._update_inventory_action_buttons()

    def _submit_inventory_action(self, action: str) -> None:
        count_id = self.inventory_count_id_var.get().strip()
        store_id = self.inventory_store_id_var.get().strip()
        if action == "START" and not store_id:
            self.inventory_error_var.set("store_id is required to start")
            return
        client = InventoryCountsClient(http=self.session._http(), access_token=self.session.token)
        try:
            if action == "START":
                keys = new_idempotency_keys()
                response = client.create_or_start_count(
                    {"store_id": store_id},
                    transaction_id=keys.transaction_id,
                    idempotency_key=keys.idempotency_key,
                )
            else:
                if not count_id:
                    self.inventory_error_var.set("count_id is required")
                    return
                keys = new_idempotency_keys()
                response = client.count_action(
                    count_id,
                    action,
                    {"action": action},
                    transaction_id=keys.transaction_id,
                    idempotency_key=keys.idempotency_key,
                    current_state=self.inventory_state.selected.state if self.inventory_state.selected else None,
                )
            self.inventory_state.selected = response
            self.inventory_count_id_var.set(response.id)
            self.inventory_lock_var.set("Store lock active" if response.lock_active else "Store lock inactive")
            self.inventory_status_var.set(f"Action {action} completed. state={response.state}")
            self.inventory_error_var.set("")
            self.inventory_trace_var.set("")
        except ApiError as exc:
            self.inventory_error_var.set(exc.message)
            self.inventory_trace_var.set(f"trace_id: {exc.trace_id}" if exc.trace_id else "")
            if "lock" in (exc.message or "").lower():
                self.inventory_status_var.set("Store is locked by an active inventory count.")
        except InventoryValidationError as exc:
            self.inventory_error_var.set(self._format_validation_issues(exc.issues))
        self._update_inventory_action_buttons()

    def _submit_inventory_scan_batch(self) -> None:
        count_id = self.inventory_count_id_var.get().strip()
        if not count_id:
            self.inventory_error_var.set("count_id is required")
            return
        try:
            qty = int((self.inventory_scan_qty_var.get() or "1").strip())
        except ValueError:
            self.inventory_error_var.set("qty must be an integer")
            return
        payload = ScanBatchRequest(items=[{"epc": self.inventory_scan_epc_var.get(), "sku": self.inventory_scan_sku_var.get(), "qty": qty}])
        try:
            validated = validate_scan_batch_payload(payload)
            keys = new_idempotency_keys()
            client = InventoryCountsClient(http=self.session._http(), access_token=self.session.token)
            response = client.submit_scan_batch(
                count_id,
                validated,
                transaction_id=keys.transaction_id,
                idempotency_key=keys.idempotency_key,
            )
            self.inventory_status_var.set(f"Scan submitted accepted={response.accepted} rejected={response.rejected}")
            self.inventory_error_var.set("")
            self.inventory_trace_var.set("")
        except InventoryValidationError as exc:
            self.inventory_error_var.set(self._format_validation_issues(exc.issues))
        except ApiError as exc:
            self.inventory_error_var.set(exc.message)
            self.inventory_trace_var.set(f"trace_id: {exc.trace_id}" if exc.trace_id else "")

    def _is_pos_allowed(self) -> bool:
        return self._has_permission("POS_SALE_VIEW", "POS_SALE_MANAGE")

    def _can_manage_pos(self) -> bool:
        return self._has_permission("POS_SALE_MANAGE")

    def _is_pos_cash_allowed(self) -> bool:
        return self._has_permission("POS_CASH_VIEW", "POS_CASH_MANAGE", "POS_CASH_DAY_CLOSE")

    def _is_reports_allowed(self) -> bool:
        return self._has_permission("REPORTS_VIEW", "reports.view")

    def _can_manage_pos_cash(self) -> bool:
        return self._has_permission("POS_CASH_MANAGE")

    def _can_day_close_pos_cash(self) -> bool:
        return self._has_permission("POS_CASH_DAY_CLOSE")

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
        ttk.Label(summary, textvariable=self.stock_action_status_var, foreground="blue").pack(anchor="w")
        ttk.Label(summary, textvariable=self.stock_action_error_var, foreground="red").pack(anchor="w")
        ttk.Label(summary, textvariable=self.stock_action_trace_var, foreground="gray").pack(anchor="w")

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

        action_frame = ttk.LabelFrame(container, text="Stock Actions", padding=10)
        action_frame.pack(fill="x", pady=(0, 10))
        action_state = tk.NORMAL if self._can_manage_stock() else tk.DISABLED
        import_epc_button = ttk.Button(
            action_frame,
            text="Import EPC",
            command=self._open_import_epc_dialog,
            state=action_state,
        )
        import_sku_button = ttk.Button(
            action_frame,
            text="Import SKU",
            command=self._open_import_sku_dialog,
            state=action_state,
        )
        migrate_button = ttk.Button(
            action_frame,
            text="Migrate SKU->EPC",
            command=self._open_migrate_dialog,
            state=action_state,
        )
        import_epc_button.pack(side="left", padx=(0, 6))
        import_sku_button.pack(side="left", padx=(0, 6))
        migrate_button.pack(side="left", padx=(0, 6))

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
        ttk.Checkbutton(
            pagination,
            text="Show images",
            variable=self.stock_show_images_var,
            command=self._populate_stock_table,
            state=state,
        ).pack(side="left", padx=(12, 0))

        table_frame = ttk.Frame(container)
        table_frame.pack(fill="both", expand=True)
        columns = (
            "image",
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
            width = 90 if col == "image" else 140
            self.stock_table.column(col, width=width, anchor="w")
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
        self.stock_action_controls = [import_epc_button, import_sku_button, migrate_button]
        if not allowed:
            self._set_stock_controls_state(tk.DISABLED)
        if not self._can_manage_stock():
            self._set_stock_action_controls_state(tk.DISABLED)

    def _set_stock_controls_state(self, state: str) -> None:
        for widget in self.stock_controls:
            widget.configure(state=state)

    def _set_stock_action_controls_state(self, state: str) -> None:
        for widget in self.stock_action_controls:
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
        user_error = to_user_facing_error(exc)
        self.stock_loading_var.set("")
        self.stock_error_var.set(user_error.message)
        self.stock_action_trace_var.set(f"trace_id: {user_error.trace_id}" if user_error.trace_id else "")
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
            media = self._resolve_row_media(row)
            image_value = media.get("thumb_url") if self.stock_show_images_var.get() else "(hidden)"
            values = (
                image_value,
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
        media = self._resolve_row_media(payload)
        payload = {**payload, "ui_media": media}
        pretty = json.dumps(payload, indent=2, default=str)
        self.stock_detail_text.delete("1.0", tk.END)
        self.stock_detail_text.insert(tk.END, pretty)

    def _resolve_row_media(self, row: dict) -> dict[str, str | None]:
        cache_key = f"stock|{row.get('sku')}|{row.get('var1_value')}|{row.get('var2_value')}"
        cached = self.stock_image_cache.get(cache_key)
        if isinstance(cached, dict):
            return cached
        source = (row.get("image_source") or "PLACEHOLDER").upper()
        image_url = safe_image_url(row.get("image_url"))
        thumb_url = safe_image_url(row.get("image_thumb_url")) or image_url
        if not image_url and row.get("sku") and self.stock_show_images_var.get():
            try:
                resolver = MediaClient(http=self.session._http(), access_token=self.session.token)
                resolved = resolver.resolve_for_variant(
                    row.get("sku"),
                    row.get("var1_value"),
                    row.get("var2_value"),
                )
                image_url = safe_image_url(resolved.resolved.url)
                thumb_url = safe_image_url(resolved.resolved.thumb_url) or image_url
                source = resolved.source
            except Exception:
                source = source or "PLACEHOLDER"
        if not thumb_url:
            thumb_url = placeholder_image_ref()
            source = "PLACEHOLDER"
        media = {
            "image_url": image_url or placeholder_image_ref(),
            "thumb_url": thumb_url,
            "source": source,
            "last_updated": str(row.get("image_updated_at") or ""),
        }
        self.stock_image_cache.set(cache_key, media)
        return media

    def _open_import_epc_dialog(self) -> None:
        self._open_stock_action_dialog(
            title="Import EPC",
            validator=validate_import_epc_line,
            submitter=self._submit_stock_import_epc,
            sample_payload=self._sample_import_epc_payload(),
            expects_single=False,
        )

    def _open_import_sku_dialog(self) -> None:
        self._open_stock_action_dialog(
            title="Import SKU",
            validator=validate_import_sku_line,
            submitter=self._submit_stock_import_sku,
            sample_payload=self._sample_import_sku_payload(),
            expects_single=False,
        )

    def _open_migrate_dialog(self) -> None:
        self._open_stock_action_dialog(
            title="Migrate SKU -> EPC",
            validator=validate_migration_line,
            submitter=self._submit_stock_migrate,
            sample_payload=self._sample_migrate_payload(),
            expects_single=True,
        )

    def _open_stock_action_dialog(
        self,
        *,
        title: str,
        validator,
        submitter,
        sample_payload: dict | list[dict],
        expects_single: bool,
    ) -> None:
        if self.root is None:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("760x560")
        dialog.grab_set()

        file_var = tk.StringVar(value="")
        status_var = tk.StringVar(value="")
        error_var = tk.StringVar(value="")
        lines: list[dict] = []
        normalized_lines: list[dict] = []

        header = ttk.Label(dialog, text=title, font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w", padx=12, pady=(12, 6))

        input_frame = ttk.LabelFrame(dialog, text="Input (JSON or CSV)", padding=8)
        input_frame.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(input_frame, text="File").grid(row=0, column=0, sticky="w")
        file_entry = ttk.Entry(input_frame, textvariable=file_var, width=60)
        file_entry.grid(row=0, column=1, sticky="ew", padx=(6, 6))

        def browse_file() -> None:
            path = filedialog.askopenfilename(
                title="Select file",
                filetypes=(("JSON", "*.json"), ("CSV", "*.csv"), ("All files", "*.*")),
            )
            if path:
                file_var.set(path)

        ttk.Button(input_frame, text="Browse", command=browse_file).grid(row=0, column=2, sticky="e")

        ttk.Label(input_frame, text="Inline JSON").grid(row=1, column=0, sticky="nw", pady=(6, 0))
        inline_text = tk.Text(input_frame, height=6, width=60)
        inline_text.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=(6, 0))

        def load_sample() -> None:
            inline_text.delete("1.0", tk.END)
            inline_text.insert(tk.END, json.dumps(sample_payload, indent=2))
            file_var.set("")

        ttk.Button(input_frame, text="Load sample", command=load_sample).grid(row=2, column=1, sticky="w", pady=(6, 0))

        input_frame.columnconfigure(1, weight=1)

        preview_frame = ttk.LabelFrame(dialog, text="Preview", padding=8)
        preview_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        columns = ("sku", "epc", "status", "location_code", "qty")
        preview_table = ttk.Treeview(preview_frame, columns=columns, show="headings", height=8)
        for col in columns:
            preview_table.heading(col, text=col.replace("_", " ").title())
            preview_table.column(col, width=120, anchor="w")
        preview_table.pack(side="left", fill="both", expand=True)
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=preview_table.yview)
        preview_table.configure(yscrollcommand=preview_scroll.set)
        preview_scroll.pack(side="right", fill="y")

        actions_frame = ttk.Frame(dialog)
        actions_frame.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Button(actions_frame, text="Load & Preview", command=lambda: load_input()).pack(side="left", padx=(0, 6))
        ttk.Button(actions_frame, text="Validate", command=lambda: validate_input()).pack(side="left", padx=(0, 6))
        ttk.Button(actions_frame, text="Submit", command=lambda: submit_input()).pack(side="left", padx=(0, 6))
        ttk.Label(actions_frame, textvariable=status_var, foreground="blue").pack(side="left", padx=(8, 0))

        ttk.Label(dialog, textvariable=error_var, foreground="red").pack(anchor="w", padx=12, pady=(0, 6))

        def load_input() -> None:
            nonlocal lines
            status_var.set("")
            error_var.set("")
            try:
                parsed = self._parse_stock_action_payload(file_var.get(), inline_text.get("1.0", tk.END), expects_single)
            except ValueError as exc:
                error_var.set(str(exc))
                return
            lines = parsed
            self._populate_preview_table(preview_table, lines)

        def validate_input() -> None:
            nonlocal normalized_lines
            status_var.set("")
            error_var.set("")
            try:
                normalized_lines = self._validate_action_lines(lines, validator)
            except ClientValidationError as exc:
                error_var.set(self._format_validation_issues(exc.issues))
                return
            status_var.set(f"Validated {len(normalized_lines)} line(s)")

        def submit_input() -> None:
            if not normalized_lines:
                validate_input()
                if not normalized_lines:
                    return
            if not messagebox.askyesno("Confirm", f"Submit {len(normalized_lines)} line(s)?"):
                return
            status_var.set("Submitting...")
            error_var.set("")
            self.stock_action_status_var.set("Submitting stock mutation...")
            self.stock_action_error_var.set("")
            self.stock_action_trace_var.set("")

            def worker() -> None:
                keys = new_idempotency_keys()
                try:
                    response = submitter(
                        normalized_lines,
                        transaction_id=keys.transaction_id,
                        idempotency_key=keys.idempotency_key,
                    )
                except ApiError as exc:
                    if self.root:
                        self.root.after(0, lambda: self._handle_stock_action_error(exc))
                    return
                if self.root:
                    self.root.after(0, lambda: self._handle_stock_action_success(response))

            threading.Thread(target=worker, daemon=True).start()
            dialog.destroy()

    def _parse_stock_action_payload(self, file_path: str, inline_json: str, expects_single: bool) -> list[dict]:
        payload: object | None = None
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".json":
                with open(file_path, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            elif ext == ".csv":
                with open(file_path, "r", encoding="utf-8", newline="") as handle:
                    payload = [self._coerce_csv_row(row) for row in csv.DictReader(handle)]
            else:
                raise ValueError("Unsupported file type; use .json or .csv")
        else:
            raw = inline_json.strip()
            if not raw:
                raise ValueError("Provide a file or inline JSON input.")
            payload = json.loads(raw)
        return self._normalize_payload_to_lines(payload, expects_single)

    def _normalize_payload_to_lines(self, payload: object, expects_single: bool) -> list[dict]:
        if isinstance(payload, dict) and "lines" in payload:
            lines = payload["lines"]
        else:
            lines = payload
        if isinstance(lines, dict):
            lines = [lines]
        if not isinstance(lines, list):
            raise ValueError("Input must be a list of lines or an object with 'lines'.")
        if expects_single and len(lines) != 1:
            raise ValueError("Migration requires exactly one payload line.")
        return [self._coerce_line_dict(line) for line in lines]

    def _coerce_line_dict(self, line: object) -> dict:
        if isinstance(line, dict):
            return line
        raise ValueError("Each line must be a JSON object.")

    def _coerce_csv_row(self, row: dict[str, str]) -> dict:
        parsed: dict[str, object] = {}
        for key, value in row.items():
            if value is None:
                parsed[key] = None
                continue
            trimmed = value.strip()
            if trimmed == "":
                parsed[key] = None
            else:
                parsed[key] = trimmed
        if "qty" in parsed and parsed["qty"] is not None:
            try:
                parsed["qty"] = int(parsed["qty"])
            except ValueError:
                pass
        if "location_is_vendible" in parsed and parsed["location_is_vendible"] is not None:
            parsed["location_is_vendible"] = str(parsed["location_is_vendible"]).lower() in {"true", "1", "yes"}
        return parsed

    def _populate_preview_table(self, table: ttk.Treeview, lines: list[dict]) -> None:
        for item in table.get_children():
            table.delete(item)
        for idx, line in enumerate(lines):
            data = line.get("data") if isinstance(line.get("data"), dict) else line
            values = (
                data.get("sku"),
                line.get("epc", data.get("epc")),
                data.get("status"),
                data.get("location_code"),
                data.get("qty", line.get("qty")),
            )
            table.insert("", "end", iid=str(idx), values=values)

    def _validate_action_lines(self, lines: list[dict], validator) -> list[dict]:
        normalized: list[dict] = []
        issues: list[ValidationIssue] = []
        if not lines:
            raise ClientValidationError([ValidationIssue(row_index=None, field="lines", reason="lines must not be empty")])
        for idx, line in enumerate(lines):
            try:
                validated = validator(line, idx)
                normalized.append(validated.model_dump(mode="json", exclude_none=True))
            except ClientValidationError as exc:
                issues.extend(exc.issues)
        if issues:
            raise ClientValidationError(issues)
        return normalized

    def _format_validation_issues(self, issues: list[ValidationIssue]) -> str:
        if not issues:
            return "Validation failed"
        return "; ".join(
            f"row {issue.row_index} {issue.field}: {issue.reason}" if issue.row_index is not None else f"{issue.field}: {issue.reason}"
            for issue in issues
        )

    def _ensure_transfer_filter_vars(self) -> None:
        if self.transfer_filter_vars:
            return
        keys = [
            "q",
            "status",
            "origin_store_id",
            "destination_store_id",
            "from",
            "to",
        ]
        self.transfer_filter_vars = {key: tk.StringVar(value="") for key in keys}

    def _collect_transfer_filters(self) -> dict[str, str | None]:
        self._ensure_transfer_filter_vars()
        filters: dict[str, str | None] = {}
        for key, var in self.transfer_filter_vars.items():
            value = var.get().strip()
            filters[key] = value if value else None
        return filters

    def _clear_transfer_filters(self) -> None:
        self._ensure_transfer_filter_vars()
        for var in self.transfer_filter_vars.values():
            var.set("")

    def _show_transfers_view(self) -> None:
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()

        self._ensure_transfer_filter_vars()
        allowed = self._is_transfers_allowed()
        can_manage = self._can_manage_transfers()
        view_state = tk.NORMAL if allowed else tk.DISABLED

        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, padding=(0, 0, 0, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Transfers", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        if not allowed:
            ttk.Label(
                header,
                text="You do not have permission to view transfers.",
                foreground="red",
            ).pack(anchor="w", pady=(4, 0))

        summary = ttk.Frame(container)
        summary.pack(fill="x", pady=(4, 8))
        ttk.Label(summary, textvariable=self.transfer_meta_var).pack(anchor="w")
        ttk.Label(summary, textvariable=self.transfer_loading_var, foreground="blue").pack(anchor="w")
        ttk.Label(summary, textvariable=self.transfer_error_var, foreground="red").pack(anchor="w")
        ttk.Label(summary, textvariable=self.transfer_action_status_var, foreground="blue").pack(anchor="w")
        ttk.Label(summary, textvariable=self.transfer_action_error_var, foreground="red").pack(anchor="w")
        ttk.Label(summary, textvariable=self.transfer_action_trace_var, foreground="gray").pack(anchor="w")

        filter_frame = ttk.LabelFrame(container, text="Filters", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))

        row = 0
        for idx, key in enumerate(["q", "status", "origin_store_id", "destination_store_id", "from", "to"]):
            label = key.replace("_", " ").title()
            ttk.Label(filter_frame, text=label).grid(row=row, column=idx * 2, sticky="w", padx=(0, 6), pady=2)
            ttk.Entry(filter_frame, textvariable=self.transfer_filter_vars[key], width=18).grid(
                row=row, column=idx * 2 + 1, sticky="ew", padx=(0, 12), pady=2
            )
            if idx == 2:
                row += 1
        for col in range(12):
            filter_frame.columnconfigure(col, weight=1)

        filter_actions = ttk.Frame(filter_frame)
        filter_actions.grid(row=row + 1, column=0, columnspan=12, sticky="w", pady=(6, 0))
        ttk.Button(filter_actions, text="Search", state=view_state, command=self._refresh_transfers).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(filter_actions, text="Clear", state=view_state, command=self._clear_transfer_filters).pack(
            side="left", padx=(0, 6)
        )

        body = ttk.Frame(container)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=3)

        table_frame = ttk.Frame(body)
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        columns = ("id", "status", "origin", "destination", "created_at", "updated_at")
        self.transfer_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=14)
        for col in columns:
            self.transfer_table.heading(col, text=col.replace("_", " ").title())
            self.transfer_table.column(col, width=120, stretch=True)
        self.transfer_table.pack(fill="both", expand=True)
        if self.transfer_table is not None:
            self.transfer_table.bind("<<TreeviewSelect>>", self._on_transfer_select)

        detail_frame = ttk.Frame(body)
        detail_frame.grid(row=0, column=1, sticky="nsew")
        ttk.Label(detail_frame, text="Details").pack(anchor="w")
        self.transfer_detail_text = tk.Text(detail_frame, height=12, wrap="word")
        self.transfer_detail_text.pack(fill="both", expand=True)

        action_frame = ttk.LabelFrame(container, text="Actions", padding=10)
        action_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(action_frame, text="Payload (JSON)").grid(row=0, column=0, sticky="w")
        self.transfer_payload_text = tk.Text(action_frame, height=8, width=80)
        self.transfer_payload_text.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(4, 8))

        self.transfer_action_buttons = {}
        button_specs = [
            ("Create", self._submit_transfer_create),
            ("Update Draft", self._submit_transfer_update),
            ("Dispatch", self._submit_transfer_dispatch),
            ("Receive", self._submit_transfer_receive),
            ("Report Shortages", self._submit_transfer_report_shortages),
            ("Resolve Shortages", self._submit_transfer_resolve_shortages),
            ("Cancel", self._submit_transfer_cancel),
            ("Refresh Detail", self._refresh_transfer_detail),
        ]
        for idx, (label, handler) in enumerate(button_specs):
            button = ttk.Button(action_frame, text=label, command=handler, state=tk.NORMAL if can_manage else tk.DISABLED)
            button.grid(row=2 + idx // 4, column=idx % 4, padx=4, pady=4, sticky="ew")
            self.transfer_action_buttons[label] = button

        action_frame.columnconfigure(0, weight=1)
        action_frame.columnconfigure(1, weight=1)
        action_frame.columnconfigure(2, weight=1)
        action_frame.columnconfigure(3, weight=1)

        self._refresh_transfers()

    def _refresh_transfers(self) -> None:
        if not self._is_transfers_allowed():
            self.transfer_error_var.set("Permission denied.")
            return
        self.transfer_loading_var.set("Loading transfers...")
        self.transfer_error_var.set("")

        filters = self._collect_transfer_filters()
        query = TransferQuery(
            q=filters.get("q"),
            status=filters.get("status"),
            origin_store_id=filters.get("origin_store_id"),
            destination_store_id=filters.get("destination_store_id"),
            from_date=filters.get("from"),
            to_date=filters.get("to"),
        )

        def worker() -> None:
            client = TransfersClient(http=self.session._http(), access_token=self.session.token)
            try:
                response = client.list_transfers(query)
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._handle_transfer_error(exc))
                return
            if self.root:
                self.root.after(0, lambda: self._handle_transfer_list_success(response))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_transfer_list_success(self, response) -> None:
        self.transfer_loading_var.set("")
        self.transfer_state.rows = self._apply_transfer_filters(response.rows)
        self.transfer_meta_var.set(f"Transfers: {len(self.transfer_state.rows)}")
        self._render_transfer_table()

    def _apply_transfer_filters(self, rows: list[TransferResponse]) -> list[TransferResponse]:
        filters = self._collect_transfer_filters()
        status = (filters.get("status") or "").upper()
        origin = filters.get("origin_store_id")
        destination = filters.get("destination_store_id")
        query = filters.get("q") or ""
        from_date = _parse_optional_datetime(filters.get("from"))
        to_date = _parse_optional_datetime(filters.get("to"))
        results = []
        for row in rows:
            header = row.header
            if status and header.status.upper() != status:
                continue
            if origin and header.origin_store_id != origin:
                continue
            if destination and header.destination_store_id != destination:
                continue
            if query and query.lower() not in header.id.lower():
                continue
            if from_date and header.created_at < from_date:
                continue
            if to_date and header.created_at > to_date:
                continue
            results.append(row)
        return results

    def _render_transfer_table(self) -> None:
        if self.transfer_table is None:
            return
        for item in self.transfer_table.get_children():
            self.transfer_table.delete(item)
        for row in self.transfer_state.rows:
            header = row.header
            values = (
                header.id,
                header.status,
                header.origin_store_id,
                header.destination_store_id,
                header.created_at,
                header.updated_at or "",
            )
            self.transfer_table.insert("", "end", iid=header.id, values=values)

    def _on_transfer_select(self, _event=None) -> None:
        if self.transfer_table is None:
            return
        selected = self.transfer_table.selection()
        if not selected:
            return
        transfer_id = selected[0]
        self.transfer_selected_id_var.set(transfer_id)
        chosen = next((row for row in self.transfer_state.rows if row.header.id == transfer_id), None)
        self.transfer_state.selected = chosen
        self._update_transfer_detail()
        self._update_transfer_action_buttons()

    def _update_transfer_detail(self) -> None:
        if self.transfer_detail_text is None:
            return
        self.transfer_detail_text.delete("1.0", tk.END)
        if not self.transfer_state.selected:
            self.transfer_detail_text.insert(tk.END, "Select a transfer to view details.")
            return
        detail = self.transfer_state.selected.model_dump(mode="json")
        self.transfer_detail_text.insert(tk.END, json.dumps(detail, indent=2, default=str))

    def _update_transfer_action_buttons(self) -> None:
        if not self.transfer_action_buttons:
            return
        selected = self.transfer_state.selected
        if not selected:
            for button in self.transfer_action_buttons.values():
                button.configure(state=tk.DISABLED)
            return
        availability = transfer_action_availability(
            selected.header.status,
            can_manage=self._can_manage_transfers(),
            is_destination_user=self._is_destination_user(selected),
        )
        mapping = {
            "Update Draft": availability.can_update,
            "Dispatch": availability.can_dispatch,
            "Receive": availability.can_receive,
            "Report Shortages": availability.can_report_shortages,
            "Resolve Shortages": availability.can_resolve_shortages,
            "Cancel": availability.can_cancel,
        }
        for label, button in self.transfer_action_buttons.items():
            if label == "Create":
                button.configure(state=tk.NORMAL if self._can_manage_transfers() else tk.DISABLED)
            elif label == "Refresh Detail":
                button.configure(state=tk.NORMAL if self._is_transfers_allowed() else tk.DISABLED)
            elif label in mapping:
                button.configure(state=tk.NORMAL if mapping[label] else tk.DISABLED)

    def _is_destination_user(self, transfer: TransferResponse) -> bool:
        store_id = self.session.user.store_id if self.session.user else None
        return bool(store_id and store_id == transfer.header.destination_store_id)

    def _refresh_transfer_detail(self) -> None:
        if not self.transfer_state.selected:
            return
        self.transfer_action_status_var.set("Refreshing transfer...")
        self.transfer_action_error_var.set("")
        self.transfer_action_trace_var.set("")

        transfer_id = self.transfer_state.selected.header.id

        def worker() -> None:
            client = TransfersClient(http=self.session._http(), access_token=self.session.token)
            try:
                response = client.get_transfer(transfer_id)
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._handle_transfer_error(exc))
                return
            if self.root:
                self.root.after(0, lambda: self._handle_transfer_action_success(response))

        threading.Thread(target=worker, daemon=True).start()

    def _parse_transfer_payload(self) -> dict:
        if not self.transfer_payload_text:
            return {}
        raw = self.transfer_payload_text.get("1.0", tk.END).strip()
        if not raw:
            return {}
        return json.loads(raw)

    def _collect_line_expectations(self, transfer: TransferResponse | None) -> dict[str, int]:
        if not transfer:
            return {}
        return {line.id: line.outstanding_qty for line in transfer.lines}

    def _collect_line_types(self, transfer: TransferResponse | None) -> dict[str, str]:
        if not transfer:
            return {}
        return {line.id: line.line_type for line in transfer.lines}

    def _submit_transfer_create(self) -> None:
        if not self._can_manage_transfers():
            return
        try:
            payload = validate_create_transfer_payload(self._parse_transfer_payload())
        except (ValueError, ClientValidationError) as exc:
            self.transfer_action_error_var.set(str(exc))
            return
        self._submit_transfer_request("create", payload)

    def _submit_transfer_update(self) -> None:
        if not self._can_manage_transfers() or not self.transfer_state.selected:
            return
        try:
            payload = validate_update_transfer_payload(self._parse_transfer_payload())
        except (ValueError, ClientValidationError) as exc:
            self.transfer_action_error_var.set(str(exc))
            return
        self._submit_transfer_request("update", payload)

    def _submit_transfer_dispatch(self) -> None:
        if not self.transfer_state.selected:
            return
        if not messagebox.askyesno("Confirm", "Dispatch this transfer?"):
            return
        try:
            payload = validate_dispatch_payload(self._parse_transfer_payload() or {})
        except (ValueError, ClientValidationError) as exc:
            self.transfer_action_error_var.set(str(exc))
            return
        self._submit_transfer_request("dispatch", payload)

    def _submit_transfer_receive(self) -> None:
        if not self.transfer_state.selected:
            return
        try:
            payload = validate_receive_payload(
                self._parse_transfer_payload(),
                line_expectations=self._collect_line_expectations(self.transfer_state.selected),
                line_types=self._collect_line_types(self.transfer_state.selected),
            )
        except (ValueError, ClientValidationError) as exc:
            self.transfer_action_error_var.set(str(exc))
            return
        self._submit_transfer_request("receive", payload)

    def _submit_transfer_report_shortages(self) -> None:
        if not self.transfer_state.selected:
            return
        try:
            payload = validate_shortage_report_payload(
                self._parse_transfer_payload(),
                line_expectations=self._collect_line_expectations(self.transfer_state.selected),
                line_types=self._collect_line_types(self.transfer_state.selected),
            )
        except (ValueError, ClientValidationError) as exc:
            self.transfer_action_error_var.set(str(exc))
            return
        self._submit_transfer_request("report_shortages", payload)

    def _submit_transfer_resolve_shortages(self) -> None:
        if not self.transfer_state.selected:
            return
        try:
            payload = validate_shortage_resolution_payload(
                self._parse_transfer_payload(),
                line_expectations=self._collect_line_expectations(self.transfer_state.selected),
                line_types=self._collect_line_types(self.transfer_state.selected),
                allow_lost_in_route=self._is_manager_role(),
            )
        except (ValueError, ClientValidationError) as exc:
            self.transfer_action_error_var.set(str(exc))
            return
        self._submit_transfer_request("resolve_shortages", payload)

    def _submit_transfer_cancel(self) -> None:
        if not self.transfer_state.selected:
            return
        if not messagebox.askyesno("Confirm", "Cancel this transfer?"):
            return
        try:
            payload = validate_cancel_payload(self._parse_transfer_payload() or {})
        except (ValueError, ClientValidationError) as exc:
            self.transfer_action_error_var.set(str(exc))
            return
        self._submit_transfer_request("cancel", payload)

    def _submit_transfer_request(self, action: str, payload) -> None:
        self.transfer_action_status_var.set(f"Submitting transfer {action}...")
        self.transfer_action_error_var.set("")
        self.transfer_action_trace_var.set("")

        transfer_id = self.transfer_state.selected.header.id if self.transfer_state.selected else None

        def worker() -> None:
            client = TransfersClient(http=self.session._http(), access_token=self.session.token)
            keys = new_idempotency_keys()
            try:
                if action == "create":
                    response = client.create_transfer(
                        payload,
                        transaction_id=keys.transaction_id,
                        idempotency_key=keys.idempotency_key,
                    )
                elif action == "update" and transfer_id:
                    response = client.update_transfer(
                        transfer_id,
                        payload,
                        transaction_id=keys.transaction_id,
                        idempotency_key=keys.idempotency_key,
                    )
                elif transfer_id:
                    response = client.transfer_action(
                        transfer_id,
                        action,
                        payload,
                        transaction_id=keys.transaction_id,
                        idempotency_key=keys.idempotency_key,
                        allow_lost_in_route=self._is_manager_role(),
                        line_expectations=self._collect_line_expectations(self.transfer_state.selected),
                        line_types=self._collect_line_types(self.transfer_state.selected),
                    )
                else:
                    raise ValueError("transfer_id is required for this action")
            except (ApiError, ClientValidationError, ValueError) as exc:
                if isinstance(exc, ApiError):
                    if self.root:
                        self.root.after(0, lambda: self._handle_transfer_error(exc))
                else:
                    if self.root:
                        self.root.after(0, lambda: self.transfer_action_error_var.set(str(exc)))
                return
            if self.root:
                self.root.after(0, lambda: self._handle_transfer_action_success(response))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_transfer_action_success(self, response: TransferResponse) -> None:
        self.transfer_action_status_var.set("Transfer updated successfully.")
        self.transfer_action_error_var.set("")
        self.transfer_action_trace_var.set("")
        self.transfer_state.selected = response
        self._update_transfer_detail()
        self._refresh_transfers()

    def _handle_transfer_error(self, exc: ApiError) -> None:
        user_error = to_user_facing_error(exc)
        self.transfer_loading_var.set("")
        self.transfer_action_status_var.set("")
        self.transfer_error_var.set(user_error.message)
        self.transfer_action_error_var.set(user_error.message)
        self.transfer_action_trace_var.set(f"trace_id: {user_error.trace_id}" if user_error.trace_id else "")

    def _show_pos_view(self) -> None:
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()

        allowed = self._is_pos_allowed()
        can_manage = self._can_manage_pos()
        view_state = tk.NORMAL if allowed else tk.DISABLED
        manage_state = tk.NORMAL if can_manage else tk.DISABLED

        container = ttk.Frame(self.content_frame)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, padding=(0, 0, 0, 8))
        header.pack(fill="x")
        ttk.Label(header, text="POS Sales", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        if not allowed:
            ttk.Label(
                header,
                text="You do not have permission to access POS sales.",
                foreground="red",
            ).pack(anchor="w", pady=(4, 0))

        status = ttk.Frame(container)
        status.pack(fill="x", pady=(4, 8))
        ttk.Label(status, textvariable=self.pos_sale_status_var).pack(anchor="w")
        ttk.Label(status, textvariable=self.pos_totals_var).pack(anchor="w")
        ttk.Label(status, textvariable=self.pos_cart_var).pack(anchor="w")
        ttk.Label(status, textvariable=self.pos_loading_var, foreground="blue").pack(anchor="w")
        ttk.Label(status, textvariable=self.pos_error_var, foreground="red").pack(anchor="w")
        ttk.Label(status, textvariable=self.pos_validation_var, foreground="red").pack(anchor="w")
        ttk.Label(status, textvariable=self.pos_trace_var, foreground="gray").pack(anchor="w")

        header_form = ttk.LabelFrame(container, text="Sale Header", padding=10)
        header_form.pack(fill="x", pady=(0, 10))
        ttk.Label(header_form, text="Store ID").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(header_form, textvariable=self.pos_store_id_var, state=view_state, width=32).grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(header_form, text=f"Currency: {self.pos_currency}").grid(row=0, column=2, sticky="w", padx=(16, 0))

        entry_frame = ttk.LabelFrame(container, text="Item Entry", padding=10)
        entry_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(entry_frame, text="Line Type").grid(row=0, column=0, sticky="w", padx=(0, 8))
        line_type = ttk.Combobox(
            entry_frame,
            textvariable=self.pos_line_type_var,
            values=("SKU", "EPC"),
            state="readonly" if allowed else "disabled",
            width=10,
        )
        line_type.grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Label(entry_frame, text="SKU").grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Entry(entry_frame, textvariable=self.pos_sku_var, state=view_state, width=18).grid(
            row=0, column=3, sticky="w"
        )
        ttk.Label(entry_frame, text="EPC").grid(row=0, column=4, sticky="w", padx=(12, 8))
        ttk.Entry(entry_frame, textvariable=self.pos_epc_var, state=view_state, width=24).grid(
            row=0, column=5, sticky="w"
        )

        ttk.Label(entry_frame, text="Qty").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        ttk.Entry(entry_frame, textvariable=self.pos_qty_var, state=view_state, width=10).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )
        ttk.Label(entry_frame, text="Unit Price").grid(row=1, column=2, sticky="w", padx=(0, 8), pady=(6, 0))
        ttk.Entry(entry_frame, textvariable=self.pos_unit_price_var, state=view_state, width=12).grid(
            row=1, column=3, sticky="w", pady=(6, 0)
        )
        ttk.Label(entry_frame, text="Location").grid(row=1, column=4, sticky="w", padx=(12, 8), pady=(6, 0))
        ttk.Entry(entry_frame, textvariable=self.pos_location_code_var, state=view_state, width=12).grid(
            row=1, column=5, sticky="w", pady=(6, 0)
        )
        ttk.Label(entry_frame, text="Pool").grid(row=1, column=6, sticky="w", padx=(12, 8), pady=(6, 0))
        ttk.Entry(entry_frame, textvariable=self.pos_pool_var, state=view_state, width=10).grid(
            row=1, column=7, sticky="w", pady=(6, 0)
        )

        entry_controls = ttk.Frame(entry_frame)
        entry_controls.grid(row=2, column=0, columnspan=8, sticky="w", pady=(8, 0))
        add_button = ttk.Button(
            entry_controls,
            text="Add line to cart",
            command=self._add_pos_line,
            state=manage_state,
        )
        remove_button = ttk.Button(
            entry_controls,
            text="Remove selected line (placeholder)",
            state=tk.DISABLED,
        )
        add_button.pack(side="left", padx=(0, 8))
        remove_button.pack(side="left")

        cart_frame = ttk.LabelFrame(container, text="Cart", padding=10)
        cart_frame.pack(fill="both", expand=True, pady=(0, 10))
        ttk.Checkbutton(
            cart_frame,
            text="Show images",
            variable=self.pos_show_images_var,
            command=self._refresh_pos_cart_table,
            state=view_state,
        ).pack(anchor="w", pady=(0, 6))
        columns = ("thumb", "line_type", "sku", "epc", "qty", "unit_price", "line_total", "source")
        self.pos_cart_table = ttk.Treeview(cart_frame, columns=columns, show="headings", height=6)
        for col in columns:
            self.pos_cart_table.heading(col, text=col.replace("_", " ").title())
            self.pos_cart_table.column(col, width=100 if col in {"thumb", "source"} else 110, anchor="w")
        self.pos_cart_table.bind("<<TreeviewSelect>>", self._on_pos_line_selected)
        self.pos_cart_table.pack(fill="both", expand=True)
        ttk.Label(cart_frame, textvariable=self.pos_image_preview_var, foreground="gray").pack(anchor="w", pady=(6, 0))
        ttk.Label(cart_frame, textvariable=self.pos_image_source_var, foreground="gray").pack(anchor="w")

        totals_frame = ttk.LabelFrame(container, text="Totals", padding=10)
        totals_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(totals_frame, textvariable=self.pos_totals_var).pack(anchor="w")

        payments_frame = ttk.LabelFrame(container, text="Payments", padding=10)
        payments_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(payments_frame, text="Cash").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(payments_frame, textvariable=self.pos_cash_amount_var, state=view_state, width=12).grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(payments_frame, text="Card").grid(row=0, column=2, sticky="w", padx=(12, 8))
        ttk.Entry(payments_frame, textvariable=self.pos_card_amount_var, state=view_state, width=12).grid(
            row=0, column=3, sticky="w"
        )
        ttk.Label(payments_frame, text="Auth Code").grid(row=0, column=4, sticky="w", padx=(12, 8))
        ttk.Entry(payments_frame, textvariable=self.pos_card_auth_var, state=view_state, width=16).grid(
            row=0, column=5, sticky="w"
        )

        ttk.Label(payments_frame, text="Transfer").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        ttk.Entry(payments_frame, textvariable=self.pos_transfer_amount_var, state=view_state, width=12).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )
        ttk.Label(payments_frame, text="Bank").grid(row=1, column=2, sticky="w", padx=(12, 8), pady=(6, 0))
        ttk.Entry(payments_frame, textvariable=self.pos_transfer_bank_var, state=view_state, width=16).grid(
            row=1, column=3, sticky="w", pady=(6, 0)
        )
        ttk.Label(payments_frame, text="Voucher").grid(row=1, column=4, sticky="w", padx=(12, 8), pady=(6, 0))
        ttk.Entry(payments_frame, textvariable=self.pos_transfer_voucher_var, state=view_state, width=16).grid(
            row=1, column=5, sticky="w", pady=(6, 0)
        )

        cash_frame = ttk.LabelFrame(container, text="Cash Drawer", padding=10)
        cash_frame.pack(fill="x", pady=(0, 10))
        cash_allowed = self._is_pos_cash_allowed()
        cash_manage_state = tk.NORMAL if self._can_manage_pos_cash() else tk.DISABLED
        cash_view_state = tk.NORMAL if cash_allowed else tk.DISABLED
        day_close_state = tk.NORMAL if self._can_day_close_pos_cash() else tk.DISABLED

        if not cash_allowed:
            ttk.Label(
                cash_frame,
                text="You do not have permission to access cash drawer operations.",
                foreground="red",
            ).pack(anchor="w")

        cash_status = ttk.Frame(cash_frame)
        cash_status.pack(fill="x")
        ttk.Label(cash_status, textvariable=self.pos_cash_status_var).pack(anchor="w")
        ttk.Label(cash_status, textvariable=self.pos_cash_meta_var).pack(anchor="w")
        ttk.Label(cash_status, textvariable=self.pos_cash_action_status_var, foreground="green").pack(anchor="w")
        ttk.Label(cash_status, textvariable=self.pos_cash_loading_var, foreground="blue").pack(anchor="w")
        ttk.Label(cash_status, textvariable=self.pos_cash_error_var, foreground="red").pack(anchor="w")
        ttk.Label(cash_status, textvariable=self.pos_cash_trace_var, foreground="gray").pack(anchor="w")

        cash_inputs = ttk.Frame(cash_frame)
        cash_inputs.pack(fill="x", pady=(8, 6))
        ttk.Label(cash_inputs, text="Business Date").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Entry(
            cash_inputs,
            textvariable=self.pos_cash_business_date_var,
            state=cash_view_state,
            width=14,
        ).grid(row=0, column=1, sticky="w")
        ttk.Label(cash_inputs, text="Timezone").grid(row=0, column=2, sticky="w", padx=(12, 6))
        ttk.Entry(
            cash_inputs,
            textvariable=self.pos_cash_timezone_var,
            state=cash_view_state,
            width=10,
        ).grid(row=0, column=3, sticky="w")
        ttk.Label(cash_inputs, text="Reason").grid(row=0, column=4, sticky="w", padx=(12, 6))
        ttk.Entry(
            cash_inputs,
            textvariable=self.pos_cash_reason_var,
            state=cash_view_state,
            width=24,
        ).grid(row=0, column=5, sticky="w")

        ttk.Label(cash_inputs, text="Opening Amount").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(
            cash_inputs,
            textvariable=self.pos_cash_opening_amount_var,
            state=cash_manage_state,
            width=14,
        ).grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Label(cash_inputs, text="Action Amount").grid(row=1, column=2, sticky="w", padx=(12, 6), pady=(6, 0))
        ttk.Entry(
            cash_inputs,
            textvariable=self.pos_cash_action_amount_var,
            state=cash_manage_state,
            width=10,
        ).grid(row=1, column=3, sticky="w", pady=(6, 0))
        ttk.Label(cash_inputs, text="Counted Cash").grid(row=1, column=4, sticky="w", padx=(12, 6), pady=(6, 0))
        ttk.Entry(
            cash_inputs,
            textvariable=self.pos_cash_counted_cash_var,
            state=cash_manage_state,
            width=12,
        ).grid(row=1, column=5, sticky="w", pady=(6, 0))
        ttk.Checkbutton(
            cash_inputs,
            text="Force day close (if open sessions)",
            variable=self.pos_cash_force_day_close_var,
            state=day_close_state,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

        cash_actions = ttk.Frame(cash_frame)
        cash_actions.pack(fill="x", pady=(4, 6))
        ttk.Button(
            cash_actions,
            text="Open Session",
            command=self._open_cash_session,
            state=cash_manage_state,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            cash_actions,
            text="Cash In",
            command=self._cash_in_session,
            state=cash_manage_state,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            cash_actions,
            text="Cash Out",
            command=self._cash_out_session,
            state=cash_manage_state,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            cash_actions,
            text="Close Session",
            command=self._close_cash_session,
            state=cash_manage_state,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            cash_actions,
            text="Day Close",
            command=self._day_close_cash,
            state=day_close_state,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            cash_actions,
            text="Refresh",
            command=self._refresh_pos_cash_data,
            state=cash_view_state,
        ).pack(side="left")

        if not self._can_day_close_pos_cash():
            ttk.Label(
                cash_frame,
                text="Day close requires POS_CASH_DAY_CLOSE permission.",
                foreground="gray",
            ).pack(anchor="w", pady=(0, 4))

        movements_frame = ttk.Frame(cash_frame)
        movements_frame.pack(fill="x")
        movement_columns = ("movement_type", "amount", "expected_after", "occurred_at", "reason")
        self.pos_cash_movements_table = ttk.Treeview(
            movements_frame,
            columns=movement_columns,
            show="headings",
            height=4,
        )
        for col in movement_columns:
            self.pos_cash_movements_table.heading(col, text=col.replace("_", " ").title())
            self.pos_cash_movements_table.column(col, width=140, anchor="w")
        self.pos_cash_movements_table.pack(fill="x", expand=True)

        action_frame = ttk.LabelFrame(container, text="Actions", padding=10)
        action_frame.pack(fill="x")
        create_button = ttk.Button(
            action_frame,
            text="Create Sale",
            command=self._create_pos_sale,
            state=manage_state,
        )
        update_button = ttk.Button(
            action_frame,
            text="Add/Update Items",
            command=self._update_pos_sale,
            state=manage_state,
        )
        checkout_button = ttk.Button(
            action_frame,
            text="Checkout",
            command=self._checkout_pos_sale,
            state=manage_state,
        )
        cancel_button = ttk.Button(
            action_frame,
            text="Cancel Sale",
            command=self._cancel_pos_sale,
            state=manage_state,
        )
        refresh_button = ttk.Button(
            action_frame,
            text="Refresh",
            command=self._refresh_pos_sale,
            state=view_state,
        )
        create_button.pack(side="left", padx=(0, 6))
        update_button.pack(side="left", padx=(0, 6))
        checkout_button.pack(side="left", padx=(0, 6))
        cancel_button.pack(side="left", padx=(0, 6))
        refresh_button.pack(side="left")

        self._update_pos_totals()
        self._refresh_pos_cart_table()
        if cash_allowed:
            self._refresh_pos_cash_data(async_mode=True)

    def _reset_pos_messages(self) -> None:
        self.pos_error_var.set("")
        self.pos_trace_var.set("")
        self.pos_validation_var.set("")

    def _set_pos_loading(self, text: str) -> None:
        self.pos_loading_var.set(text)

    def _parse_decimal(self, value: str, fallback: Decimal = Decimal("0.00")) -> Decimal:
        try:
            return Decimal(value.strip())
        except Exception:
            return fallback

    def _parse_optional_decimal(self, value: str) -> Decimal | None:
        raw = value.strip()
        if not raw:
            return None
        try:
            return Decimal(raw)
        except Exception:
            return None

    def _format_payment_issues(self, issues: list[PaymentValidationIssue]) -> str:
        if not issues:
            return ""
        return "\n".join(f"{issue.field}: {issue.reason}" for issue in issues)

    def _format_cash_validation_issues(self, issues: list[CashValidationIssue]) -> str:
        if not issues:
            return ""
        return "; ".join(f"{issue.field}: {issue.reason}" for issue in issues)

    def _format_cash_session_status(self, session: PosCashSessionSummary | None) -> str:
        if session is None:
            return "Cash session: NONE"
        status = session.status or "UNKNOWN"
        return f"Cash session: {status} (id={session.id})"

    def _format_cash_session_meta(self, session: PosCashSessionSummary | None) -> str:
        if session is None:
            return "No active cash session."
        parts = [
            f"cashier={session.cashier_user_id}",
            f"opened_at={session.opened_at}",
            f"opening_amount={session.opening_amount}",
            f"expected_cash={session.expected_cash}",
        ]
        return " | ".join(part for part in parts if part and "None" not in str(part))

    def _reset_pos_cash_messages(self) -> None:
        self.pos_cash_error_var.set("")
        self.pos_cash_trace_var.set("")
        self.pos_cash_action_status_var.set("")

    def _set_pos_cash_loading(self, text: str) -> None:
        self.pos_cash_loading_var.set(text)

    def _apply_pos_cash_session(self, session: PosCashSessionSummary | None) -> None:
        self.pos_cash_state.session = session
        self.pos_cash_status_var.set(self._format_cash_session_status(session))
        self.pos_cash_meta_var.set(self._format_cash_session_meta(session))

    def _apply_pos_cash_movements(self, movements: list[PosCashMovementResponse]) -> None:
        self.pos_cash_state.movements = movements
        self._refresh_cash_movements_table()

    def _refresh_cash_movements_table(self) -> None:
        if self.pos_cash_movements_table is None:
            return
        for row in self.pos_cash_movements_table.get_children():
            self.pos_cash_movements_table.delete(row)
        for movement in self.pos_cash_state.movements:
            self.pos_cash_movements_table.insert(
                "",
                "end",
                values=(
                    movement.movement_type,
                    movement.amount,
                    movement.expected_balance_after,
                    movement.occurred_at,
                    movement.reason,
                ),
            )

    def _current_pos_total_due(self) -> Decimal:
        if self.pos_state.sale and self.pos_state.sale.header.total_due is not None:
            return Decimal(str(self.pos_state.sale.header.total_due))
        subtotal = Decimal("0.00")
        for line in self.pos_state.lines:
            subtotal += Decimal(str(line.unit_price)) * Decimal(line.qty)
        return subtotal

    def _update_pos_totals(self) -> None:
        subtotal = self._current_pos_total_due()
        payments = self._collect_pos_payments()
        validation = validate_checkout_payload(total_due=subtotal, payments=payments) if payments else None
        paid_total = validation.totals.paid_total if validation else Decimal("0.00")
        missing = validation.totals.missing_amount if validation else subtotal
        change = validation.totals.change_due if validation else Decimal("0.00")
        totals_text = (
            f"Totals: subtotal={subtotal:.2f} total_due={subtotal:.2f} "
            f"paid_total={paid_total:.2f} missing={missing:.2f} change={change:.2f}"
        )
        self.pos_totals_var.set(totals_text)
        self.pos_cart_var.set(f"Cart lines: {len(self.pos_state.lines)}")

    def _refresh_pos_cart_table(self) -> None:
        if self.pos_cart_table is None:
            return
        for row in self.pos_cart_table.get_children():
            self.pos_cart_table.delete(row)
        for line in self.pos_state.lines:
            snapshot = line.snapshot
            line_total = Decimal(str(line.unit_price)) * Decimal(line.qty)
            media = self._resolve_snapshot_media(snapshot)
            self.pos_cart_table.insert(
                "",
                "end",
                values=(
                    media["thumb_url"] if self.pos_show_images_var.get() else "(hidden)",
                    line.line_type,
                    snapshot.sku if snapshot else None,
                    snapshot.epc if snapshot else None,
                    line.qty,
                    f"{Decimal(str(line.unit_price)):.2f}",
                    f"{line_total:.2f}",
                    media["source"],
                ),
            )

    def _resolve_snapshot_media(self, snapshot: PosSaleLineSnapshot | None) -> dict[str, str]:
        if snapshot is None:
            return {"thumb_url": placeholder_image_ref(), "image_url": placeholder_image_ref(), "source": "PLACEHOLDER"}
        source = (snapshot.image_source or "PLACEHOLDER").upper()
        image_url = safe_image_url(snapshot.image_url)
        thumb_url = safe_image_url(snapshot.image_thumb_url) or image_url
        if not thumb_url and snapshot.sku and self.pos_show_images_var.get():
            try:
                resolver = MediaClient(http=self.session._http(), access_token=self.session.token)
                resolved = resolver.resolve_for_variant(snapshot.sku, snapshot.var1_value, snapshot.var2_value)
                image_url = safe_image_url(resolved.resolved.url)
                thumb_url = safe_image_url(resolved.resolved.thumb_url) or image_url
                source = resolved.source
            except Exception:
                source = source or "PLACEHOLDER"
        if not thumb_url:
            thumb_url = placeholder_image_ref()
            image_url = image_url or placeholder_image_ref()
            source = "PLACEHOLDER"
        return {"thumb_url": thumb_url, "image_url": image_url or thumb_url, "source": source}

    def _on_pos_line_selected(self, _event: tk.Event) -> None:
        if self.pos_cart_table is None:
            return
        selected = self.pos_cart_table.selection()
        if not selected:
            return
        idx = self.pos_cart_table.index(selected[0])
        if idx >= len(self.pos_state.lines):
            return
        media = self._resolve_snapshot_media(self.pos_state.lines[idx].snapshot)
        self.pos_image_preview_var.set(f"Image: {media['image_url']}")
        self.pos_image_source_var.set(f"Source: {media['source']}")

    def _refresh_pos_cash_data(self, *, client: PosCashClient | None = None, async_mode: bool = True) -> None:
        if not self._is_pos_cash_allowed():
            return
        store_id = self.pos_store_id_var.get().strip() or None
        if not store_id:
            self.pos_cash_error_var.set("Store ID is required for cash session actions.")
            return
        if not store_id:
            self.pos_cash_error_var.set("Store ID is required to load cash session.")
            return
        self._reset_pos_cash_messages()

        def worker() -> None:
            try:
                api_client = client or PosCashClient(http=self.session._http(), access_token=self.session.token)
                current = api_client.get_current_session(store_id=store_id)
                movements = api_client.get_movements(store_id=store_id, limit=10)
                session = current.session
                if self.root:
                    self.root.after(0, lambda: self._apply_pos_cash_session(session))
                    self.root.after(0, lambda: self._apply_pos_cash_movements(movements.rows))
                else:
                    self._apply_pos_cash_session(session)
                    self._apply_pos_cash_movements(movements.rows)
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_api_error(exc))
                else:
                    self._set_pos_cash_api_error(exc)
            finally:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_loading(""))
                else:
                    self._set_pos_cash_loading("")

        self._set_pos_cash_loading("Loading cash session...")
        if async_mode:
            threading.Thread(target=worker, daemon=True).start()
        else:
            worker()

    def _set_pos_cash_api_error(self, exc: ApiError) -> None:
        user_error = to_user_facing_error(exc)
        self.pos_cash_error_var.set(user_error.message)
        self.pos_cash_trace_var.set(f"trace_id: {user_error.trace_id}" if user_error.trace_id else "")

    def _open_cash_session(self, *, client: PosCashClient | None = None, async_mode: bool = True) -> None:
        if not self._can_manage_pos_cash():
            return
        self._reset_pos_cash_messages()
        store_id = self.pos_store_id_var.get().strip() or None
        if not store_id:
            self.pos_cash_error_var.set("Store ID is required for cash session actions.")
            return
        opening_amount = self._parse_optional_decimal(self.pos_cash_opening_amount_var.get())
        business_date = self.pos_cash_business_date_var.get().strip() or None
        timezone = self.pos_cash_timezone_var.get().strip() or None
        reason = self.pos_cash_reason_var.get().strip() or None
        validation = validate_open_session_payload(
            store_id=store_id,
            opening_amount=opening_amount,
            business_date=business_date,
            timezone=timezone,
        )
        if not validation.ok:
            self.pos_cash_error_var.set(self._format_cash_validation_issues(validation.issues))
            return
        keys = new_idempotency_keys()
        payload = {
            "transaction_id": keys.transaction_id,
            "store_id": store_id,
            "action": "OPEN",
            "opening_amount": str(opening_amount),
            "business_date": business_date,
            "timezone": timezone,
            "reason": reason,
        }

        def worker() -> None:
            try:
                api_client = client or PosCashClient(http=self.session._http(), access_token=self.session.token)
                session = api_client.cash_action("OPEN", payload, idempotency_key=keys.idempotency_key)
                if self.root:
                    self.root.after(0, lambda: self._apply_pos_cash_session(session))
                    self.root.after(0, lambda: self.pos_cash_action_status_var.set("Cash session opened."))
                    self.root.after(0, lambda: self._refresh_pos_cash_data(client=api_client, async_mode=False))
                else:
                    self._apply_pos_cash_session(session)
                    self.pos_cash_action_status_var.set("Cash session opened.")
                    self._refresh_pos_cash_data(client=api_client, async_mode=False)
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_api_error(exc))
                else:
                    self._set_pos_cash_api_error(exc)
            finally:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_loading(""))
                else:
                    self._set_pos_cash_loading("")

        self._set_pos_cash_loading("Opening cash session...")
        if async_mode:
            threading.Thread(target=worker, daemon=True).start()
        else:
            worker()

    def _cash_in_session(self, *, client: PosCashClient | None = None, async_mode: bool = True) -> None:
        if not self._can_manage_pos_cash():
            return
        self._reset_pos_cash_messages()
        store_id = self.pos_store_id_var.get().strip() or None
        if not store_id:
            self.pos_cash_error_var.set("Store ID is required for cash session actions.")
            return
        amount = self._parse_optional_decimal(self.pos_cash_action_amount_var.get())
        reason = self.pos_cash_reason_var.get().strip() or None
        validation = validate_cash_in_payload(amount, reason)
        if not validation.ok:
            self.pos_cash_error_var.set(self._format_cash_validation_issues(validation.issues))
            return
        keys = new_idempotency_keys()
        payload = {
            "transaction_id": keys.transaction_id,
            "store_id": store_id,
            "action": "CASH_IN",
            "amount": str(amount),
            "reason": reason,
        }

        def worker() -> None:
            try:
                api_client = client or PosCashClient(http=self.session._http(), access_token=self.session.token)
                session = api_client.cash_action("CASH_IN", payload, idempotency_key=keys.idempotency_key)
                if self.root:
                    self.root.after(0, lambda: self._apply_pos_cash_session(session))
                    self.root.after(0, lambda: self.pos_cash_action_status_var.set("Cash in recorded."))
                    self.root.after(0, lambda: self._refresh_pos_cash_data(client=api_client, async_mode=False))
                else:
                    self._apply_pos_cash_session(session)
                    self.pos_cash_action_status_var.set("Cash in recorded.")
                    self._refresh_pos_cash_data(client=api_client, async_mode=False)
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_api_error(exc))
                else:
                    self._set_pos_cash_api_error(exc)
            finally:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_loading(""))
                else:
                    self._set_pos_cash_loading("")

        self._set_pos_cash_loading("Recording cash in...")
        if async_mode:
            threading.Thread(target=worker, daemon=True).start()
        else:
            worker()

    def _cash_out_session(self, *, client: PosCashClient | None = None, async_mode: bool = True) -> None:
        if not self._can_manage_pos_cash():
            return
        self._reset_pos_cash_messages()
        store_id = self.pos_store_id_var.get().strip() or None
        if not store_id:
            self.pos_cash_error_var.set("Store ID is required for cash session actions.")
            return
        amount = self._parse_optional_decimal(self.pos_cash_action_amount_var.get())
        reason = self.pos_cash_reason_var.get().strip() or None
        expected_balance = None
        if self.pos_cash_state.session and self.pos_cash_state.session.expected_cash is not None:
            expected_balance = Decimal(str(self.pos_cash_state.session.expected_cash))
        validation = validate_cash_out_payload(amount, reason, expected_balance=expected_balance)
        if not validation.ok:
            self.pos_cash_error_var.set(self._format_cash_validation_issues(validation.issues))
            return
        keys = new_idempotency_keys()
        payload = {
            "transaction_id": keys.transaction_id,
            "store_id": store_id,
            "action": "CASH_OUT",
            "amount": str(amount),
            "reason": reason,
        }

        def worker() -> None:
            try:
                api_client = client or PosCashClient(http=self.session._http(), access_token=self.session.token)
                session = api_client.cash_action("CASH_OUT", payload, idempotency_key=keys.idempotency_key)
                if self.root:
                    self.root.after(0, lambda: self._apply_pos_cash_session(session))
                    self.root.after(0, lambda: self.pos_cash_action_status_var.set("Cash out recorded."))
                    self.root.after(0, lambda: self._refresh_pos_cash_data(client=api_client, async_mode=False))
                else:
                    self._apply_pos_cash_session(session)
                    self.pos_cash_action_status_var.set("Cash out recorded.")
                    self._refresh_pos_cash_data(client=api_client, async_mode=False)
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_api_error(exc))
                else:
                    self._set_pos_cash_api_error(exc)
            finally:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_loading(""))
                else:
                    self._set_pos_cash_loading("")

        self._set_pos_cash_loading("Recording cash out...")
        if async_mode:
            threading.Thread(target=worker, daemon=True).start()
        else:
            worker()

    def _close_cash_session(self, *, client: PosCashClient | None = None, async_mode: bool = True) -> None:
        if not self._can_manage_pos_cash():
            return
        self._reset_pos_cash_messages()
        store_id = self.pos_store_id_var.get().strip() or None
        if not store_id:
            self.pos_cash_error_var.set("Store ID is required for cash session actions.")
            return
        counted_cash = self._parse_optional_decimal(self.pos_cash_counted_cash_var.get())
        reason = self.pos_cash_reason_var.get().strip() or None
        validation = validate_close_session_payload(counted_cash, reason)
        if not validation.ok:
            self.pos_cash_error_var.set(self._format_cash_validation_issues(validation.issues))
            return
        keys = new_idempotency_keys()
        payload = {
            "transaction_id": keys.transaction_id,
            "store_id": store_id,
            "action": "CLOSE",
            "counted_cash": str(counted_cash),
            "reason": reason,
        }

        def worker() -> None:
            try:
                api_client = client or PosCashClient(http=self.session._http(), access_token=self.session.token)
                session = api_client.cash_action("CLOSE", payload, idempotency_key=keys.idempotency_key)
                if self.root:
                    self.root.after(0, lambda: self._apply_pos_cash_session(session))
                    self.root.after(0, lambda: self.pos_cash_action_status_var.set("Cash session closed."))
                    self.root.after(0, lambda: self._refresh_pos_cash_data(client=api_client, async_mode=False))
                else:
                    self._apply_pos_cash_session(session)
                    self.pos_cash_action_status_var.set("Cash session closed.")
                    self._refresh_pos_cash_data(client=api_client, async_mode=False)
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_api_error(exc))
                else:
                    self._set_pos_cash_api_error(exc)
            finally:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_loading(""))
                else:
                    self._set_pos_cash_loading("")

        self._set_pos_cash_loading("Closing cash session...")
        if async_mode:
            threading.Thread(target=worker, daemon=True).start()
        else:
            worker()

    def _day_close_cash(self, *, client: PosCashClient | None = None, async_mode: bool = True) -> None:
        if not self._can_day_close_pos_cash():
            return
        self._reset_pos_cash_messages()
        store_id = self.pos_store_id_var.get().strip() or None
        business_date = self.pos_cash_business_date_var.get().strip() or None
        timezone = self.pos_cash_timezone_var.get().strip() or None
        counted_cash = self._parse_optional_decimal(self.pos_cash_counted_cash_var.get())
        reason = self.pos_cash_reason_var.get().strip() or None
        validation = validate_day_close_payload(
            store_id=store_id,
            business_date=business_date,
            timezone=timezone,
            counted_cash=counted_cash,
            reason=reason,
        )
        if not validation.ok:
            self.pos_cash_error_var.set(self._format_cash_validation_issues(validation.issues))
            return
        keys = new_idempotency_keys()
        payload = {
            "transaction_id": keys.transaction_id,
            "store_id": store_id,
            "action": "CLOSE_DAY",
            "business_date": business_date,
            "timezone": timezone,
            "force_if_open_sessions": self.pos_cash_force_day_close_var.get(),
            "reason": reason,
        }
        if counted_cash is not None:
            payload["counted_cash"] = str(counted_cash)

        def worker() -> None:
            try:
                api_client = client or PosCashClient(http=self.session._http(), access_token=self.session.token)
                response = api_client.day_close(payload, idempotency_key=keys.idempotency_key)
                if self.root:
                    self.root.after(0, lambda: self.pos_cash_action_status_var.set("Day close completed."))
                    self.root.after(0, lambda: self._refresh_pos_cash_data(client=api_client, async_mode=False))
                else:
                    self.pos_cash_action_status_var.set("Day close completed.")
                    self._refresh_pos_cash_data(client=api_client, async_mode=False)
                self.pos_cash_state.last_day_close = response
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_api_error(exc))
                else:
                    self._set_pos_cash_api_error(exc)
            finally:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_cash_loading(""))
                else:
                    self._set_pos_cash_loading("")

        self._set_pos_cash_loading("Closing business day...")
        if async_mode:
            threading.Thread(target=worker, daemon=True).start()
        else:
            worker()

    def _build_pos_line(self) -> PosSaleLineCreate | None:
        self._reset_pos_messages()
        line_type = self.pos_line_type_var.get().strip().upper() or "SKU"
        qty = int(self._parse_decimal(self.pos_qty_var.get(), Decimal("1")))
        unit_price = self._parse_decimal(self.pos_unit_price_var.get(), Decimal("0.00"))
        sku = self.pos_sku_var.get().strip() or None
        epc = self.pos_epc_var.get().strip() or None
        location_code = self.pos_location_code_var.get().strip()
        pool = self.pos_pool_var.get().strip()
        issues: list[str] = []
        if qty < 1:
            issues.append("qty must be at least 1")
        if unit_price < 0:
            issues.append("unit_price must be >= 0")
        if line_type == "EPC":
            if qty != 1:
                issues.append("EPC qty must be 1")
            if not epc:
                issues.append("epc is required for EPC lines")
        if line_type == "SKU" and epc:
            issues.append("epc must be empty for SKU lines")
        if not location_code or not pool:
            issues.append("location_code and pool are required")
        if issues:
            self.pos_validation_var.set("; ".join(issues))
            return None
        status = "RFID" if line_type == "EPC" else "PENDING"
        snapshot = PosSaleLineSnapshot(
            sku=sku,
            description=None,
            var1_value=None,
            var2_value=None,
            epc=epc,
            location_code=location_code,
            pool=pool,
            status=status,
            location_is_vendible=True,
        )
        return PosSaleLineCreate(line_type=line_type, qty=qty, unit_price=unit_price, snapshot=snapshot)

    def _add_pos_line(self) -> None:
        if not self._can_manage_pos():
            return
        line = self._build_pos_line()
        if line is None:
            return
        self.pos_state.lines.append(line)
        self._update_pos_totals()
        self._refresh_pos_cart_table()

    def _collect_pos_payments(self) -> list[PosPaymentCreate]:
        payments: list[PosPaymentCreate] = []
        cash_amount = self._parse_decimal(self.pos_cash_amount_var.get())
        if cash_amount > 0:
            payments.append(PosPaymentCreate(method="CASH", amount=cash_amount))
        card_amount = self._parse_decimal(self.pos_card_amount_var.get())
        if card_amount > 0:
            payments.append(
                PosPaymentCreate(
                    method="CARD",
                    amount=card_amount,
                    authorization_code=self.pos_card_auth_var.get().strip() or None,
                )
            )
        transfer_amount = self._parse_decimal(self.pos_transfer_amount_var.get())
        if transfer_amount > 0:
            payments.append(
                PosPaymentCreate(
                    method="TRANSFER",
                    amount=transfer_amount,
                    bank_name=self.pos_transfer_bank_var.get().strip() or None,
                    voucher_number=self.pos_transfer_voucher_var.get().strip() or None,
                )
            )
        return payments

    def _apply_sale_response(self, response: PosSaleResponse) -> None:
        self.pos_state.sale = response
        header = response.header
        self.pos_sale_status_var.set(
            f"Sale {header.id} status={header.status} total_due={header.total_due} paid={header.paid_total}"
        )
        mapped_lines: list[PosSaleLineCreate] = []
        for line in response.lines:
            if not line.snapshot or line.unit_price is None:
                continue
            mapped_lines.append(
                PosSaleLineCreate(
                    line_type=line.line_type or "SKU",
                    qty=line.qty or 1,
                    unit_price=Decimal(str(line.unit_price)),
                    snapshot=line.snapshot,
                )
            )
        if mapped_lines:
            self.pos_state.lines = mapped_lines
        self._update_pos_totals()
        self._refresh_pos_cart_table()

    def _create_pos_sale(self) -> None:
        if not self._can_manage_pos():
            return
        if self.pos_state.busy:
            self.pos_validation_var.set("Checkout already in progress.")
            return
        self._reset_pos_messages()
        self.pos_state.busy = True
        if not self.pos_state.lines:
            self.pos_validation_var.set("Add at least one line before creating a sale.")
            return
        store_id = self.pos_store_id_var.get().strip()
        if not store_id:
            self.pos_validation_var.set("Store ID is required.")
            return
        keys = new_idempotency_keys()
        payload = {
            "transaction_id": keys.transaction_id,
            "store_id": store_id,
            "lines": [line.model_dump(mode="json", exclude_none=True) for line in self.pos_state.lines],
        }

        def worker() -> None:
            try:
                client = PosSalesClient(http=self.session._http(), access_token=self.session.token)
                response = client.create_sale(payload, idempotency_key=keys.idempotency_key)
                if self.root:
                    self.root.after(0, lambda: self._apply_sale_response(response))
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_api_error(exc))
            finally:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_loading(""))

        self._set_pos_loading("Creating sale...")
        threading.Thread(target=worker, daemon=True).start()

    def _update_pos_sale(self) -> None:
        if not self._can_manage_pos():
            return
        if self.pos_state.busy:
            self.pos_validation_var.set("Checkout already in progress.")
            return
        self._reset_pos_messages()
        self.pos_state.busy = True
        sale = self.pos_state.sale
        if sale is None:
            self.pos_validation_var.set("Create a sale before updating items.")
            return
        keys = new_idempotency_keys()
        payload = {
            "transaction_id": keys.transaction_id,
            "lines": [line.model_dump(mode="json", exclude_none=True) for line in self.pos_state.lines],
        }

        def worker() -> None:
            try:
                client = PosSalesClient(http=self.session._http(), access_token=self.session.token)
                response = client.update_sale(sale.header.id, payload, idempotency_key=keys.idempotency_key)
                if self.root:
                    self.root.after(0, lambda: self._apply_sale_response(response))
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_api_error(exc))
            finally:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_loading(""))

        self._set_pos_loading("Updating sale lines...")
        threading.Thread(target=worker, daemon=True).start()

    def _checkout_pos_sale(
        self,
        *,
        client: PosSalesClient | None = None,
        cash_client: PosCashClient | None = None,
    ) -> None:
        if not self._can_manage_pos():
            return
        if self.pos_state.busy:
            self.pos_validation_var.set("Checkout already in progress.")
            return
        self._reset_pos_messages()
        self.pos_state.busy = True
        sale = self.pos_state.sale
        if sale is None:
            self.pos_validation_var.set("Create a sale before checkout.")
            return
        payments = self._collect_pos_payments()
        validation = validate_checkout_payload(total_due=self._current_pos_total_due(), payments=payments)
        if not validation.ok:
            self.pos_validation_var.set(self._format_payment_issues(validation.issues))
            return
        if validation.totals.cash_total > 0:
            cash_client = cash_client or PosCashClient(http=self.session._http(), access_token=self.session.token)
            try:
                current = cash_client.get_current_session(store_id=self.pos_store_id_var.get().strip() or None)
            except ApiError as exc:
                self._set_pos_api_error(exc)
                return
            if current.session is None or current.session.status != "OPEN":
                self.pos_validation_var.set("CASH checkout requires an open cash session.")
                return
        keys = new_idempotency_keys()
        payload = {
            "transaction_id": keys.transaction_id,
            "action": "checkout",
            "payments": [payment.model_dump(mode="json", exclude_none=True) for payment in payments],
        }
        client = client or PosSalesClient(http=self.session._http(), access_token=self.session.token)
        try:
            response = client.sale_action(
                sale.header.id,
                "checkout",
                payload,
                idempotency_key=keys.idempotency_key,
            )
            self._apply_sale_response(response)
        except ApiError as exc:
            self._set_pos_api_error(exc)
        finally:
            self.pos_state.busy = False

    def _cancel_pos_sale(self, *, client: PosSalesClient | None = None) -> None:
        if not self._can_manage_pos():
            return
        if self.pos_state.busy:
            self.pos_validation_var.set("Checkout already in progress.")
            return
        self._reset_pos_messages()
        self.pos_state.busy = True
        sale = self.pos_state.sale
        if sale is None:
            self.pos_validation_var.set("Create a sale before cancel.")
            return
        keys = new_idempotency_keys()
        payload = {"transaction_id": keys.transaction_id, "action": "cancel"}
        client = client or PosSalesClient(http=self.session._http(), access_token=self.session.token)
        try:
            response = client.sale_action(sale.header.id, "cancel", payload, idempotency_key=keys.idempotency_key)
            self._apply_sale_response(response)
        except ApiError as exc:
            self._set_pos_api_error(exc)
        finally:
            self.pos_state.busy = False

    def _refresh_pos_sale(self) -> None:
        if not self._is_pos_allowed():
            return
        sale = self.pos_state.sale
        if sale is None:
            self.pos_validation_var.set("No sale loaded to refresh.")
            return
        self._reset_pos_messages()

        def worker() -> None:
            try:
                client = PosSalesClient(http=self.session._http(), access_token=self.session.token)
                response = client.get_sale(sale.header.id)
                if self.root:
                    self.root.after(0, lambda: self._apply_sale_response(response))
            except ApiError as exc:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_api_error(exc))
            finally:
                if self.root:
                    self.root.after(0, lambda: self._set_pos_loading(""))

        self._set_pos_loading("Refreshing sale...")
        threading.Thread(target=worker, daemon=True).start()

    def _set_pos_api_error(self, exc: ApiError) -> None:
        self.pos_error_var.set(f"{exc.code}: {exc.message}")
        if exc.details:
            self.pos_validation_var.set(json.dumps(exc.details, indent=2))
        self.pos_trace_var.set(f"trace_id: {exc.trace_id}")

    def _submit_stock_import_epc(
        self,
        lines: list[dict],
        *,
        transaction_id: str,
        idempotency_key: str,
        client: StockClient | None = None,
    ):
        api_client = client or StockClient(http=self.session._http(), access_token=self.session.token)
        return api_client.import_epc(lines, transaction_id=transaction_id, idempotency_key=idempotency_key)

    def _submit_stock_import_sku(
        self,
        lines: list[dict],
        *,
        transaction_id: str,
        idempotency_key: str,
        client: StockClient | None = None,
    ):
        api_client = client or StockClient(http=self.session._http(), access_token=self.session.token)
        return api_client.import_sku(lines, transaction_id=transaction_id, idempotency_key=idempotency_key)

    def _submit_stock_migrate(
        self,
        lines: list[dict],
        *,
        transaction_id: str,
        idempotency_key: str,
        client: StockClient | None = None,
    ):
        api_client = client or StockClient(http=self.session._http(), access_token=self.session.token)
        return api_client.migrate_sku_to_epc(lines, transaction_id=transaction_id, idempotency_key=idempotency_key)

    def _handle_stock_action_success(self, response) -> None:
        processed = getattr(response, "processed", None)
        migrated = getattr(response, "migrated", None)
        count = processed if processed is not None else migrated
        if count is not None:
            self.stock_action_status_var.set(f"Stock action completed. Count={count}")
        else:
            self.stock_action_status_var.set("Stock action completed.")
        self.stock_action_error_var.set("")
        self.stock_action_trace_var.set(f"trace_id={response.trace_id}")
        if getattr(response, "line_results", None):
            error_lines = [line for line in response.line_results or [] if line.status not in {None, "SUCCESS"}]
            if error_lines:
                self.stock_action_error_var.set(f"{len(error_lines)} line(s) failed. See details in logs.")
        self._fetch_stock(reset_page=False)

    def _handle_stock_action_error(self, exc: ApiError) -> None:
        self.stock_action_status_var.set("")
        self.stock_action_error_var.set(str(exc))
        self.stock_action_trace_var.set(f"trace_id={exc.trace_id}" if exc.trace_id else "")

    def _sample_import_epc_payload(self) -> list[dict]:
        return [
            {
                "sku": "SKU-1",
                "description": "Blue Jacket",
                "var1_value": "Blue",
                "var2_value": "L",
                "epc": "A" * 24,
                "location_code": "LOC-1",
                "pool": "P1",
                "status": "RFID",
                "location_is_vendible": True,
                "image_asset_id": None,
                "image_url": None,
                "image_thumb_url": None,
                "image_source": None,
                "image_updated_at": None,
                "qty": 1,
            }
        ]

    def _sample_import_sku_payload(self) -> list[dict]:
        return [
            {
                "sku": "SKU-1",
                "description": "Blue Jacket",
                "var1_value": "Blue",
                "var2_value": "L",
                "epc": None,
                "location_code": "LOC-1",
                "pool": "P1",
                "status": "PENDING",
                "location_is_vendible": True,
                "image_asset_id": None,
                "image_url": None,
                "image_thumb_url": None,
                "image_source": None,
                "image_updated_at": None,
                "qty": 1,
            }
        ]

    def _sample_migrate_payload(self) -> dict:
        return {
            "epc": "B" * 24,
            "data": {
                "sku": "SKU-1",
                "description": "Blue Jacket",
                "var1_value": "Blue",
                "var2_value": "L",
                "epc": None,
                "location_code": "LOC-1",
                "pool": "P1",
                "status": "PENDING",
                "location_is_vendible": True,
                "image_asset_id": None,
                "image_url": None,
                "image_thumb_url": None,
                "image_source": None,
                "image_updated_at": None,
            },
        }



    def _show_reports_view(self) -> None:
        if self.content_frame is None:
            return
        for child in self.content_frame.winfo_children():
            child.destroy()
        container = ttk.Frame(self.content_frame, padding=16)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text="Reports", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
        if not self._is_reports_allowed():
            ttk.Label(container, text="Missing REPORTS_VIEW permission. Request access from an administrator.", foreground="gray").pack(anchor="w", pady=(8, 0))
            return

        filters = ttk.LabelFrame(container, text="Filters", padding=10)
        filters.pack(fill="x", pady=(8, 8))
        row1 = ttk.Frame(filters)
        row1.pack(fill="x")
        for label, var in (("Store", self.reports_store_id_var), ("From", self.reports_from_var), ("To", self.reports_to_var), ("Timezone", self.reports_timezone_var)):
            cell = ttk.Frame(row1)
            cell.pack(side="left", padx=(0, 8))
            ttk.Label(cell, text=label).pack(anchor="w")
            ttk.Entry(cell, textvariable=var, width=16).pack(anchor="w")

        row2 = ttk.Frame(filters)
        row2.pack(fill="x", pady=(8, 0))
        for label, var in (("Grouping", self.reports_grouping_var), ("Payment", self.reports_payment_method_var)):
            cell = ttk.Frame(row2)
            cell.pack(side="left", padx=(0, 8))
            ttk.Label(cell, text=label).pack(anchor="w")
            ttk.Entry(cell, textvariable=var, width=16).pack(anchor="w")

        ttk.Checkbutton(row2, text="Business date mode", variable=self.reports_business_mode_var).pack(side="left", padx=(8, 8))
        ttk.Button(filters, text="Today", command=lambda: self._apply_report_preset(0)).pack(side="left", padx=(0, 6), pady=(8, 0))
        ttk.Button(filters, text="7d", command=lambda: self._apply_report_preset(6)).pack(side="left", padx=(0, 6), pady=(8, 0))
        ttk.Button(filters, text="30d", command=lambda: self._apply_report_preset(29)).pack(side="left", padx=(0, 6), pady=(8, 0))
        ttk.Button(filters, text="Apply Filters", command=self._load_reports).pack(side="left", padx=(12, 6), pady=(8, 0))
        ttk.Button(filters, text="Reset", command=self._reset_report_filters).pack(side="left", pady=(8, 0))

        ttk.Label(container, textvariable=self.reports_loading_var, foreground="gray").pack(anchor="w")
        ttk.Label(container, textvariable=self.reports_error_var, foreground="red").pack(anchor="w")
        ttk.Label(container, textvariable=self.reports_trace_var, foreground="gray").pack(anchor="w")
        ttk.Label(container, textvariable=self.reports_kpi_var).pack(anchor="w", pady=(6, 4))

        table_frame = ttk.LabelFrame(container, text="Daily Results", padding=8)
        table_frame.pack(fill="both", expand=True)
        self.reports_table = ttk.Treeview(table_frame, columns=("business_date", "net_sales", "orders_paid_count", "net_profit"), show="headings", height=8)
        for col, title in (("business_date", "Date"), ("net_sales", "Net Sales"), ("orders_paid_count", "Orders"), ("net_profit", "Net Profit")):
            self.reports_table.heading(col, text=title, command=lambda c=col: self._sort_reports_rows(c))
            self.reports_table.column(col, width=120, anchor="center")
        self.reports_table.pack(fill="x")

        breakdown = ttk.LabelFrame(container, text="Calendar Breakdown", padding=8)
        breakdown.pack(fill="both", expand=True, pady=(8, 0))
        self.reports_breakdown_table = ttk.Treeview(breakdown, columns=("business_date", "net_sales", "orders_paid_count"), show="headings", height=6)
        for col, title in (("business_date", "Date"), ("net_sales", "Net Sales"), ("orders_paid_count", "Orders")):
            self.reports_breakdown_table.heading(col, text=title)
            self.reports_breakdown_table.column(col, width=120, anchor="center")
        self.reports_breakdown_table.pack(fill="x")

        export_panel = ttk.LabelFrame(container, text="Export Manager", padding=10)
        export_panel.pack(fill="x", pady=(8, 0))
        ttk.Entry(export_panel, textvariable=self.reports_type_var, width=18).pack(side="left", padx=(0, 8))
        ttk.Entry(export_panel, textvariable=self.reports_format_var, width=8).pack(side="left", padx=(0, 8))
        ttk.Button(export_panel, text="Request Export", command=self._request_report_export).pack(side="left", padx=(0, 8))
        ttk.Button(export_panel, text="Refresh", command=self._refresh_export_statuses).pack(side="left", padx=(0, 8))
        ttk.Button(export_panel, text="Retry Failed", command=self._retry_failed_export).pack(side="left", padx=(0, 8))
        ttk.Button(export_panel, text="Open Artifact", command=self._open_latest_export_artifact).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(export_panel, text="Auto poll", variable=self.reports_auto_poll_var).pack(side="left")

        self.reports_export_table = ttk.Treeview(container, columns=("export_id", "status", "created", "source", "format"), show="headings", height=5)
        for col, title in (("export_id", "Export ID"), ("status", "Status"), ("created", "Created"), ("source", "Type"), ("format", "Format")):
            self.reports_export_table.heading(col, text=title)
            self.reports_export_table.column(col, width=120, anchor="center")
        self.reports_export_table.pack(fill="x", pady=(6, 0))
        ttk.Label(container, textvariable=self.reports_export_status_var, justify="left").pack(anchor="w", pady=(8, 0))

    def _reset_report_filters(self) -> None:
        self.reports_store_id_var.set(os.getenv("ARIS3_REPORTS_DEFAULT_STORE_ID", ""))
        self.reports_from_var.set("")
        self.reports_to_var.set("")
        self.reports_timezone_var.set(os.getenv("ARIS3_REPORTS_DEFAULT_TIMEZONE", "UTC"))
        self.reports_grouping_var.set("")
        self.reports_payment_method_var.set("")
        self.reports_business_mode_var.set(False)

    def _apply_report_preset(self, days_back: int) -> None:
        end_date = date.today()
        start_date = end_date.fromordinal(end_date.toordinal() - days_back)
        self.reports_from_var.set(start_date.isoformat())
        self.reports_to_var.set(end_date.isoformat())

    def _report_filter_payload(self) -> ReportFilter:
        payload = normalize_report_filters(
            {
                "store_id": self.reports_store_id_var.get().strip() or None,
                "from": self.reports_from_var.get().strip() or None,
                "to": self.reports_to_var.get().strip() or None,
                "timezone": self.reports_timezone_var.get().strip() or None,
                "payment_method": self.reports_payment_method_var.get().strip() or None,
                "grouping": self.reports_grouping_var.get().strip() or None,
                "business_date_mode": "business" if self.reports_business_mode_var.get() else None,
            }
        )
        self.reports_state.filter = payload
        return payload

    def _load_reports(self) -> None:
        payload = self._report_filter_payload()
        self.reports_loading_var.set("Loading reports…")
        self.reports_error_var.set("")
        self.reports_trace_var.set("")

        def _run() -> None:
            try:
                client = ReportsClient(http=self.session._http(), access_token=self.session.token)
                daily = client.get_sales_daily(payload)
                calendar = client.get_sales_calendar(payload)
                self.reports_state.daily = daily
                self.reports_state.calendar = calendar
                self.root and self.root.after(0, self._render_reports_loaded)
            except Exception as exc:
                def _err():
                    self.reports_loading_var.set("")
                    if isinstance(exc, ApiError):
                        self.reports_error_var.set(exc.message)
                        self.reports_trace_var.set(f"trace_id: {exc.trace_id}" if exc.trace_id else "")
                    else:
                        self.reports_error_var.set(str(exc))
                self.root and self.root.after(0, _err)

        threading.Thread(target=_run, daemon=True).start()

    def _sort_reports_rows(self, column: str) -> None:
        self.reports_state.sort_desc = not self.reports_state.sort_desc if self.reports_state.sort_column == column else False
        self.reports_state.sort_column = column
        self._render_reports_loaded()

    def _render_reports_loaded(self) -> None:
        self.reports_loading_var.set("")
        daily = self.reports_state.daily
        calendar = self.reports_state.calendar
        if daily is None:
            return
        totals = daily.totals
        self.reports_kpi_var.set(
            f"net={totals.net_sales} gross={totals.gross_sales} returns={totals.refunds_total} orders={totals.orders_paid_count} avg={totals.average_ticket}"
        )
        rows = list(daily.rows)
        key = self.reports_state.sort_column
        rows.sort(key=lambda item: getattr(item, key), reverse=self.reports_state.sort_desc)
        if self.reports_table is not None:
            for item in self.reports_table.get_children():
                self.reports_table.delete(item)
            for row in rows:
                self.reports_table.insert("", "end", values=(row.business_date.isoformat(), str(row.net_sales), row.orders_paid_count, str(row.net_profit)))
        if self.reports_breakdown_table is not None:
            for item in self.reports_breakdown_table.get_children():
                self.reports_breakdown_table.delete(item)
            for row in (calendar.rows if calendar else []):
                self.reports_breakdown_table.insert("", "end", values=(row.business_date.isoformat(), str(row.net_sales), row.orders_paid_count))

    def _render_exports(self) -> None:
        if self.reports_export_table is not None:
            for item in self.reports_export_table.get_children():
                self.reports_export_table.delete(item)
            for status in self.reports_state.exports[:20]:
                self.reports_export_table.insert(
                    "",
                    "end",
                    values=(status.export_id, status.status, status.created_at.isoformat(), status.source_type, status.format),
                )
        self.reports_export_status_var.set("\n".join([f"{it.export_id} {it.status} {it.format}" for it in self.reports_state.exports[:5]]))

    def _refresh_export_statuses(self) -> None:
        client = ExportsClient(http=self.session._http(), access_token=self.session.token)
        rows = client.list_recent_exports(page_size=20).rows
        self.reports_state.exports = rows
        self._render_exports()

    def _retry_failed_export(self) -> None:
        failed = next((x for x in self.reports_state.exports if x.status.upper() == "FAILED"), None)
        if failed is None:
            self.reports_error_var.set("No failed export to retry.")
            return
        self.reports_type_var.set(failed.source_type)
        self.reports_format_var.set(failed.format)
        self._request_report_export()

    def _open_latest_export_artifact(self) -> None:
        if not self.reports_state.exports:
            return
        client = ExportsClient(http=self.session._http(), access_token=self.session.token)
        artifact = client.resolve_export_artifact(self.reports_state.exports[0])
        self.reports_export_status_var.set(f"artifact: {artifact.url or artifact.reference or 'n/a'}")

    def _request_report_export(self) -> None:
        payload = self._report_filter_payload()
        fmt = (self.reports_format_var.get().strip() or "csv").lower()
        source = (self.reports_type_var.get().strip() or "reports_daily").lower()
        keys = new_idempotency_keys()
        try:
            client = ExportsClient(http=self.session._http(), access_token=self.session.token)
            status = client.request_export(
                {"source_type": source, "format": fmt, "filters": payload.model_dump(by_alias=True, mode="json", exclude_none=True), "transaction_id": keys.transaction_id},
                idempotency_key=keys.idempotency_key,
            )
            self.reports_state.exports.insert(0, status)
            if self.reports_auto_poll_var.get():
                result = client.wait_for_export_ready(
                    status.export_id,
                    timeout_sec=float(os.getenv("EXPORT_WAIT_TIMEOUT_SEC", "30")),
                    poll_interval_sec=float(os.getenv("EXPORT_POLL_INTERVAL_SEC", "2")),
                )
                status = result.status
                if result.outcome != ExportTerminalState.COMPLETED:
                    self.reports_error_var.set(f"Export not completed: {result.outcome.value}")
            self.reports_state.exports = [status] + [it for it in self.reports_state.exports if it.export_id != status.export_id]
            self._render_exports()
            self.reports_error_var.set("")
            self.reports_trace_var.set(f"trace_id: {status.trace_id}" if status.trace_id else "")
        except ApiError as exc:
            self.reports_error_var.set(exc.message)
            self.reports_trace_var.set(f"trace_id: {exc.trace_id}" if exc.trace_id else "")


def main() -> None:
    app = CoreAppShell()
    app.start()


if __name__ == "__main__":
    main()
