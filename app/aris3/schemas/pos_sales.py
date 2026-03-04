from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, WithJsonSchema, field_serializer


POSMoney = Annotated[
    Decimal,
    PlainSerializer(lambda value: format(value.quantize(Decimal("0.01")), "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "number"},
                {"type": "string", "pattern": r"^-?\d+\.\d{1,2}$"},
            ]
        },
        mode="validation",
    ),
    WithJsonSchema({"type": "string", "pattern": r"^-?\d+\.\d{2}$"}, mode="serialization"),
]

_MONEY_FIELD_DESCRIPTION = "Money serializado como string decimal de 2 decimales"


def money_field(*examples: str) -> Field:
    return Field(description=_MONEY_FIELD_DESCRIPTION, examples=list(examples) or ["0.00", "25.00", "125.50", "-10.00"])


class PosBaseModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json")
    def serialize_decimals(self, value):
        if isinstance(value, Decimal):
            return format(value.quantize(Decimal("0.01")), "f")
        return value


class PosSaleLineSnapshot(PosBaseModel):
    sku: str | None = None
    description: str | None = None
    var1_value: str | None = None
    var2_value: str | None = None
    epc: str | None = None
    location_code: str | None = None
    pool: str | None = None
    status: str | None = None
    location_is_vendible: bool = True
    image_asset_id: UUID | None = None
    image_url: str | None = None
    image_thumb_url: str | None = None
    image_source: str | None = None
    image_updated_at: datetime | None = None


class PosSaleLineCreate(PosBaseModel):
    line_type: Literal["EPC", "SKU"]
    qty: int = 1
    # canonical selector fields
    sku: str | None = Field(default=None, description="Canonical selector for SKU lines")
    epc: str | None = Field(default=None, description="Canonical selector for EPC lines")
    # legacy compatibility fields (transitional)
    unit_price: POSMoney | None = Field(default=None, description=_MONEY_FIELD_DESCRIPTION, examples=["25.00", "125.50"])
    status: str | None = Field(default=None)
    location_code: str | None = Field(default=None)
    pool: str | None = Field(default=None)
    snapshot: PosSaleLineSnapshot | None = Field(
        default=None,
        description="Legacy snapshot input; backend always rebuilds authoritative snapshot from stock",
    )


class PosPaymentCreate(PosBaseModel):
    method: Literal["CASH", "CARD", "TRANSFER"]
    amount: POSMoney = money_field("25.00", "125.50")
    authorization_code: str | None = None
    bank_name: str | None = None
    voucher_number: str | None = None


class PosSaleCreateRequest(PosBaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None)
    store_id: str | None = None
    lines: list[PosSaleLineCreate]


class PosSaleUpdateRequest(PosBaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None)
    lines: list[PosSaleLineCreate] | None = None


class PosReturnItem(PosBaseModel):
    line_id: str
    qty: int = 1
    condition: str


class PosSaleActionRequest(PosBaseModel):
    transaction_id: str | None
    tenant_id: str | None = Field(default=None)
    action: Literal["checkout", "cancel", "CHECKOUT", "CANCEL", "REFUND_ITEMS", "EXCHANGE_ITEMS"] = Field(
        description="Acciones permitidas: CHECKOUT, CANCEL, REFUND_ITEMS (deprecated), EXCHANGE_ITEMS (deprecated).",
        examples=["CHECKOUT", "CANCEL"],
    )
    payments: list[PosPaymentCreate] | None = None
    refund_payments: list[PosPaymentCreate] | None = Field(default=None, description="Reembolsos para devoluciones o cambios con saldo a favor del cliente")
    return_items: list[PosReturnItem] | None = Field(default=None, description="Líneas originales a devolver")
    exchange_lines: list[PosSaleLineCreate] | None = Field(default=None, description="Nuevas líneas para cambio")
    receipt_number: str | None = Field(default=None, description="Número de recibo/ticket para checkout y devoluciones")
    manager_override: bool | None = None


class PosSaleHeaderResponse(PosBaseModel):
    id: str
    tenant_id: str
    store_id: str
    status: str
    business_date: date | None = None
    timezone: str | None = None
    total_due: POSMoney = money_field("0.00", "125.50")
    paid_total: POSMoney = money_field("0.00", "125.50")
    balance_due: POSMoney = money_field("0.00")
    change_due: POSMoney = money_field("0.00", "25.00")
    receipt_number: str | None = None
    created_by_user_id: str | None
    updated_by_user_id: str | None
    checked_out_by_user_id: str | None
    canceled_by_user_id: str | None
    checked_out_at: datetime | None
    canceled_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class PosSaleLineResponse(PosBaseModel):
    id: str
    line_type: str
    qty: int
    unit_price: POSMoney = money_field("25.00", "125.50")
    line_total: POSMoney = money_field("25.00", "125.50")
    returned_qty: int = 0
    returnable_qty: int = 0
    snapshot: PosSaleLineSnapshot
    created_at: datetime


class PosPaymentResponse(PosBaseModel):
    id: str
    method: str
    amount: POSMoney = money_field("25.00", "125.50")
    authorization_code: str | None
    bank_name: str | None
    voucher_number: str | None
    created_at: datetime


class PosPaymentSummary(PosBaseModel):
    method: str
    amount: POSMoney = money_field("25.00", "125.50")


class PosReturnTotals(PosBaseModel):
    subtotal: POSMoney = money_field("0.00", "125.50")
    restocking_fee: POSMoney = money_field("0.00", "25.00")
    total: POSMoney = money_field("0.00", "125.50")


class PosReturnEventSummary(PosBaseModel):
    id: str
    action: str
    refund_total: POSMoney = money_field("0.00", "125.50")
    exchange_total: POSMoney = money_field("0.00", "125.50")
    net_adjustment: POSMoney = money_field("-10.00", "0.00", "25.00")
    created_at: datetime


class PosSaleResponse(PosBaseModel):
    header: PosSaleHeaderResponse
    lines: list[PosSaleLineResponse]
    payments: list[PosPaymentResponse]
    payment_summary: list[PosPaymentSummary]
    refunded_totals: PosReturnTotals
    exchanged_totals: PosReturnTotals
    net_adjustment: POSMoney = money_field("-10.00", "0.00", "25.00")
    return_events: list[PosReturnEventSummary]


class PosSaleListResponse(PosBaseModel):
    page: int
    page_size: int
    total: int
    rows: list[PosSaleResponse]

# shared alias for returns module
SaleLineSelector = PosSaleLineCreate

