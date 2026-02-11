from __future__ import annotations

from dataclasses import dataclass

from services.permissions_service import PermissionGate


@dataclass(frozen=True)
class ModuleSpec:
    key: str
    label: str
    required_permissions: tuple[str, ...]


MODULE_SPECS: tuple[ModuleSpec, ...] = (
    ModuleSpec("stock", "Stock", ("stock.view", "STORE_VIEW")),
    ModuleSpec("transfers", "Transfers", ("transfers.view", "TRANSFER_VIEW")),
    ModuleSpec("pos_sales", "POS Sales", ("pos.sales.view", "POS_SALE_VIEW")),
    ModuleSpec("pos_cash", "POS Cash", ("pos.cash.view", "POS_CASH_VIEW")),
    ModuleSpec("inventory_counts", "Inventory Counts", ("inventory.counts.view", "INVENTORY_COUNTS_VIEW")),
    ModuleSpec("reports", "Reports", ("reports.view", "REPORTS_VIEW")),
    ModuleSpec("exports", "Exports", ("exports.view", "EXPORT_VIEW")),
    ModuleSpec("admin", "Admin/Settings", ("admin.settings.view", "ADMIN_SETTINGS_VIEW")),
)


def allowed_modules(gate: PermissionGate) -> list[ModuleSpec]:
    return [module for module in MODULE_SPECS if gate.allows_any(*module.required_permissions)]
