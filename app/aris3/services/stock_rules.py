from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.aris3.db.models import StockItem


OperationalMode = Literal["EPC", "SKU", "NONE"]


@dataclass(frozen=True)
class StockOperationalState:
    available_for_sale: bool
    available_for_transfer: bool
    sale_mode: OperationalMode
    transfer_mode: OperationalMode
    is_historical: bool


def is_historical_status(status: str | None) -> bool:
    return (status or "").upper() == "SOLD"


def compute_operational_state(item: StockItem) -> StockOperationalState:
    status = (item.status or "").upper()
    epc = (item.epc or "").strip() or None

    if status == "SOLD":
        return StockOperationalState(
            available_for_sale=False,
            available_for_transfer=False,
            sale_mode="NONE",
            transfer_mode="NONE",
            is_historical=True,
        )

    if epc:
        return StockOperationalState(
            available_for_sale=True,
            available_for_transfer=True,
            sale_mode="EPC",
            transfer_mode="EPC",
            is_historical=False,
        )

    if not epc:
        return StockOperationalState(
            available_for_sale=True,
            available_for_transfer=True,
            sale_mode="SKU",
            transfer_mode="SKU",
            is_historical=False,
        )


def sale_epc_filters(*, tenant_id: str, store_id: str, epc: str):
    return (
        StockItem.tenant_id == tenant_id,
        StockItem.store_id == store_id,
        StockItem.epc == epc,
        StockItem.status != "SOLD",
    )


def sale_sku_filters(*, tenant_id: str, store_id: str, sku: str):
    return (
        StockItem.tenant_id == tenant_id,
        StockItem.store_id == store_id,
        StockItem.sku == sku,
        StockItem.epc.is_(None),
        StockItem.status != "SOLD",
    )


def transfer_epc_filters(*, tenant_id: str, origin_store_id: str, epc: str):
    return (
        StockItem.tenant_id == tenant_id,
        StockItem.store_id == origin_store_id,
        StockItem.epc == epc,
        StockItem.status != "SOLD",
    )


def transfer_sku_filters(*, tenant_id: str, origin_store_id: str, sku: str, location_code: str | None, pool: str | None):
    clauses = [
        StockItem.tenant_id == tenant_id,
        StockItem.store_id == origin_store_id,
        StockItem.epc.is_(None),
        StockItem.status != "SOLD",
        StockItem.sku == sku,
    ]
    if location_code is not None:
        clauses.append(StockItem.location_code == location_code)
    if pool is not None:
        clauses.append(StockItem.pool == pool)
    return tuple(clauses)
