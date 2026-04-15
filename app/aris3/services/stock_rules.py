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
    vendible = bool(item.location_is_vendible)
    in_transit = item.location_code == "IN_TRANSIT" or item.pool == "IN_TRANSIT"

    if status == "SOLD":
        return StockOperationalState(
            available_for_sale=False,
            available_for_transfer=False,
            sale_mode="NONE",
            transfer_mode="NONE",
            is_historical=True,
        )

    if status == "RFID" and epc:
        return StockOperationalState(
            available_for_sale=vendible and not in_transit,
            available_for_transfer=not in_transit,
            sale_mode="EPC" if vendible and not in_transit else "NONE",
            transfer_mode="EPC" if not in_transit else "NONE",
            is_historical=False,
        )

    if status == "PENDING" and not epc:
        return StockOperationalState(
            available_for_sale=vendible and not in_transit,
            available_for_transfer=not in_transit,
            sale_mode="SKU" if vendible and not in_transit else "NONE",
            transfer_mode="SKU" if not in_transit else "NONE",
            is_historical=False,
        )

    # Explicitly non-operational ambiguous stock (for example RFID without EPC).
    return StockOperationalState(
        available_for_sale=False,
        available_for_transfer=False,
        sale_mode="NONE",
        transfer_mode="NONE",
        is_historical=False,
    )


def sale_epc_filters(*, tenant_id: str, store_id: str, epc: str):
    return (
        StockItem.tenant_id == tenant_id,
        StockItem.store_id == store_id,
        StockItem.epc == epc,
        StockItem.status == "RFID",
        StockItem.location_is_vendible.is_(True),
        StockItem.location_code != "IN_TRANSIT",
        StockItem.pool != "IN_TRANSIT",
    )


def sale_sku_filters(*, tenant_id: str, store_id: str, sku: str):
    return (
        StockItem.tenant_id == tenant_id,
        StockItem.store_id == store_id,
        StockItem.sku == sku,
        StockItem.epc.is_(None),
        StockItem.status == "PENDING",
        StockItem.location_is_vendible.is_(True),
        StockItem.location_code != "IN_TRANSIT",
        StockItem.pool != "IN_TRANSIT",
    )


def transfer_epc_filters(*, tenant_id: str, origin_store_id: str, epc: str):
    return (
        StockItem.tenant_id == tenant_id,
        StockItem.store_id == origin_store_id,
        StockItem.epc == epc,
        StockItem.status == "RFID",
        StockItem.location_code != "IN_TRANSIT",
        StockItem.pool != "IN_TRANSIT",
    )


def transfer_sku_filters(*, tenant_id: str, origin_store_id: str, sku: str, location_code: str | None, pool: str | None):
    clauses = [
        StockItem.tenant_id == tenant_id,
        StockItem.store_id == origin_store_id,
        StockItem.epc.is_(None),
        StockItem.status == "PENDING",
        StockItem.sku == sku,
        StockItem.location_code != "IN_TRANSIT",
        StockItem.pool != "IN_TRANSIT",
    ]
    if location_code is not None:
        clauses.append(StockItem.location_code == location_code)
    if pool is not None:
        clauses.append(StockItem.pool == pool)
    return tuple(clauses)
