from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer, WithJsonSchema


MoneyValue = Annotated[
    Decimal,
    Field(ge=0, max_digits=12, decimal_places=2),
    PlainSerializer(lambda value: format(value.quantize(Decimal("0.01")), "f"), return_type=str, when_used="json"),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "number", "minimum": 0},
                {"type": "string", "pattern": r"^\d{1,10}(?:\.\d{1,2})?$"},
            ]
        },
        mode="validation",
    ),
    WithJsonSchema({"type": "string", "pattern": r"^\d{1,10}(?:\.\d{2})?$"}, mode="serialization"),
]


_MONEY_FIELD_DESCRIPTION = "Acepta number o string decimal en request; se serializa como string decimal en responses"


_STOCK_CANONICAL_EXAMPLE = {
    "sku": "SKU-1",
    "description": "Blue Jacket",
    "var1_value": "Blue",
    "var2_value": "L",
    "cost_price": "25.00",
    "suggested_price": "35.00",
    "sale_price": "32.50",
    "epc": "ABCDEFABCDEFABCDEFABCDEF",
    "location_code": "LOC-1",
    "pool": "SALE",
    "store_id": "7fa2f29e-3ffd-4e52-a0a5-8f53d0ae1a61",
    "status": "RFID",
    "location_is_vendible": True,
    "image_asset_id": "7fa2f29e-3ffd-4e52-a0a5-8f53d0ae1a61",
    "image_url": "https://example.com/image.png",
    "image_thumb_url": "https://example.com/thumb.png",
    "image_source": "catalog",
    "image_updated_at": "2025-01-01T00:00:00Z",
}

_STOCK_ROW_CANONICAL_EXAMPLE = {
    **_STOCK_CANONICAL_EXAMPLE,
    "id": "fef5d8de-0f6f-4a64-b6ce-8fcdb4128ffb",
    "tenant_id": "eec4e17f-d5f0-489f-a1c1-7f6ad5039f22",
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:05:00Z",
}

_STOCK_PENDING_CANONICAL_EXAMPLE = {
    "sku": "SKU-1",
    "description": "Blue Jacket",
    "var1_value": "Blue",
    "var2_value": "L",
    "cost_price": "25.00",
    "suggested_price": "35.00",
    "sale_price": "32.50",
    "epc": None,
    "location_code": "LOC-1",
    "pool": "SALE",
    "store_id": "7fa2f29e-3ffd-4e52-a0a5-8f53d0ae1a61",
    "status": "PENDING",
    "location_is_vendible": True,
    "image_asset_id": "7fa2f29e-3ffd-4e52-a0a5-8f53d0ae1a61",
    "image_url": "https://example.com/image.png",
    "image_thumb_url": "https://example.com/thumb.png",
    "image_source": "catalog",
    "image_updated_at": "2025-01-01T00:00:00Z",
}


class StockRow(BaseModel):
    sku: str | None
    description: str | None
    var1_value: str | None
    var2_value: str | None
    cost_price: MoneyValue | None = Field(default=None, examples=["25.00"], description=_MONEY_FIELD_DESCRIPTION)
    suggested_price: MoneyValue | None = Field(default=None, examples=["35.00"], description=_MONEY_FIELD_DESCRIPTION)
    sale_price: MoneyValue | None = Field(default=None, examples=["32.50"], description=_MONEY_FIELD_DESCRIPTION)
    epc: str | None
    location_code: str | None
    pool: str | None
    store_id: str | None
    store_name: str | None = None
    is_current_store: bool | None = None
    status: str | None
    location_is_vendible: bool
    image_asset_id: str | None
    image_url: str | None
    image_thumb_url: str | None
    image_source: str | None
    image_updated_at: datetime | None
    available_for_sale: bool
    available_for_transfer: bool
    sale_mode: Literal["EPC", "SKU", "NONE"]
    transfer_mode: Literal["EPC", "SKU", "NONE"]
    is_historical: bool
    available_qty: int
    display_pool: str | None
    display_location_code: str | None
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime | None

    model_config = {
        "json_schema_extra": {
            "example": _STOCK_ROW_CANONICAL_EXAMPLE,
            "examples": [_STOCK_ROW_CANONICAL_EXAMPLE],
        }
    }


class StockQueryMeta(BaseModel):
    page: int
    page_size: int
    sort_by: str
    sort_dir: Literal["asc", "desc"]
    scope: Literal["self", "tenant"]
    view: Literal["operational", "history", "all"]


class StockTotalsByStore(BaseModel):
    store_id: str | None
    store_name: str | None = None
    is_current_store: bool | None = None
    total_rows: int


class StockQueryTotals(BaseModel):
    total_rows: int
    total_rfid: int
    total_pending: int
    total_units: int
    totals_by_store: list[StockTotalsByStore] = Field(default_factory=list)


class StockQueryResponse(BaseModel):
    meta: StockQueryMeta
    rows: list[StockRow]
    totals: StockQueryTotals


class StockDataBlock(BaseModel):
    sku: str | None
    description: str | None
    var1_value: str | None
    var2_value: str | None
    cost_price: MoneyValue | None = Field(default=None, examples=["25.00"], description=_MONEY_FIELD_DESCRIPTION)
    suggested_price: MoneyValue | None = Field(default=None, examples=["35.00"], description=_MONEY_FIELD_DESCRIPTION)
    sale_price: MoneyValue | None = Field(default=None, examples=["32.50"], description=_MONEY_FIELD_DESCRIPTION)
    epc: str | None
    location_code: str | None = None
    pool: str | None = None
    store_id: str | None = None
    status: str | None
    location_is_vendible: bool | None = None
    image_asset_id: UUID | None
    image_url: str | None
    image_thumb_url: str | None
    image_source: str | None
    image_updated_at: datetime | None

    model_config = {
        "json_schema_extra": {
            "example": _STOCK_CANONICAL_EXAMPLE,
            "examples": [_STOCK_CANONICAL_EXAMPLE],
        }
    }


class StockImportEpcLine(StockDataBlock):
    qty: int


class StockImportSkuLine(StockDataBlock):
    epc: str | None = None
    qty: int


class StockImportEpcRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    lines: list[StockImportEpcLine]

    model_config = {
        "json_schema_extra": {
            "example": {
                "transaction_id": "tx-import-epc-001",
                "tenant_id": "eec4e17f-d5f0-489f-a1c1-7f6ad5039f22",
                "lines": [
                    {
                        **_STOCK_CANONICAL_EXAMPLE,
                        "qty": 1,
                    }
                ],
            },
            "examples": [
                {
                    "transaction_id": "tx-import-epc-001",
                    "tenant_id": "eec4e17f-d5f0-489f-a1c1-7f6ad5039f22",
                    "lines": [{**_STOCK_CANONICAL_EXAMPLE, "qty": 1}],
                },
                {
                    "transaction_id": "tx-import-epc-defaults-001",
                    "tenant_id": "eec4e17f-d5f0-489f-a1c1-7f6ad5039f22",
                    "lines": [
                        {
                            "sku": "SKU-1",
                            "description": "Blue Jacket",
                            "var1_value": "Blue",
                            "var2_value": "L",
                            "epc": "ABCDEFABCDEFABCDEFABCDEF",
                            "status": "RFID",
                            "qty": 1
                        }
                    ],
                },
            ],
        }
    }


class StockImportSkuRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    lines: list[StockImportSkuLine]

    model_config = {
        "json_schema_extra": {
            "example": {
                "transaction_id": "tx-import-sku-001",
                "tenant_id": "eec4e17f-d5f0-489f-a1c1-7f6ad5039f22",
                "lines": [
                    {
                        **_STOCK_PENDING_CANONICAL_EXAMPLE,
                        "qty": 2,
                    }
                ],
            },
            "examples": [
                {
                    "transaction_id": "tx-import-sku-001",
                    "tenant_id": "eec4e17f-d5f0-489f-a1c1-7f6ad5039f22",
                    "lines": [{**_STOCK_PENDING_CANONICAL_EXAMPLE, "qty": 2}],
                },
                {
                    "transaction_id": "tx-import-sku-defaults-001",
                    "tenant_id": "eec4e17f-d5f0-489f-a1c1-7f6ad5039f22",
                    "lines": [
                        {
                            "sku": "SKU-1",
                            "description": "Blue Jacket",
                            "var1_value": "Blue",
                            "var2_value": "L",
                            "status": "PENDING",
                            "qty": 2
                        }
                    ],
                },
            ],
        }
    }


class StockImportResponse(BaseModel):
    tenant_id: str
    processed: int
    trace_id: str


class StockMigrateRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    epc: str
    data: StockDataBlock

    model_config = {
        "json_schema_extra": {
            "example": {
                "transaction_id": "tx-migrate-001",
                "tenant_id": "eec4e17f-d5f0-489f-a1c1-7f6ad5039f22",
                "epc": "ABCDEFABCDEFABCDEFABCDEF",
                "data": _STOCK_PENDING_CANONICAL_EXAMPLE,
            },
            "examples": [
                {
                    "transaction_id": "tx-migrate-001",
                    "tenant_id": "eec4e17f-d5f0-489f-a1c1-7f6ad5039f22",
                    "epc": "ABCDEFABCDEFABCDEFABCDEF",
                    "data": _STOCK_PENDING_CANONICAL_EXAMPLE,
                }
            ],
        }
    }


class StockMigrateResponse(BaseModel):
    tenant_id: str
    migrated: int
    trace_id: str


class StockActionWriteOffPayload(BaseModel):
    reason: str | None
    qty: int = 1
    data: StockDataBlock


class StockActionRepricePayload(BaseModel):
    data: StockDataBlock
    price: float | None = None
    currency: str | None = None


class StockActionMarkdownPayload(BaseModel):
    data: StockDataBlock
    policy: str | None = None


class StockActionReprintPayload(BaseModel):
    data: StockDataBlock


class StockActionReplaceEpcPayload(BaseModel):
    current_epc: str
    new_epc: str
    reason: str | None = None


class StockActionEpcLifecyclePayload(BaseModel):
    epc: str
    reason: str | None = None
    epc_type: Literal["NON_REUSABLE_LABEL", "REUSABLE_TAG"] | None = None


class StockActionRequest(BaseModel):
    transaction_id: str | None
    tenant_id: str | None = None
    action: Literal[
        "WRITE_OFF",
        "REPRICE",
        "MARKDOWN_BY_AGE",
        "REPRINT_LABEL",
        "REPLACE_EPC",
        "MARK_EPC_DAMAGED",
        "RETIRE_EPC",
        "RETURN_EPC_TO_POOL",
    ]
    payload: dict


class StockActionResponse(BaseModel):
    tenant_id: str
    action: str
    processed: int
    trace_id: str


class PreloadLineInput(BaseModel):
    sku: str | None = None
    epc: str | None = None
    description: str | None = None
    var1_value: str | None = None
    var2_value: str | None = None
    pool: str | None = None
    location_code: str | None = None
    vendible: bool = True
    cost_price: MoneyValue | None = None
    suggested_price: MoneyValue | None = None
    sale_price: MoneyValue | None = None
    observation: str | None = None
    image_mode: Literal["existing", "replace", "add", "blank"] = "blank"
    image_asset_id: UUID | None = None
    source_row_number: int | None = None
    qty: int = 1


class PreloadSessionCreateRequest(BaseModel):
    tenant_id: str | None = None
    store_id: str | None = None
    source_file_name: str | None = None
    lines: list[PreloadLineInput]


class PreloadLineResponse(BaseModel):
    id: str
    preload_session_id: str
    item_uid: str
    tenant_id: str
    store_id: str | None
    sku: str | None
    epc: str | None
    description: str | None
    var1_value: str | None
    var2_value: str | None
    pool: str | None
    location_code: str | None
    vendible: bool
    cost_price: MoneyValue | None = None
    suggested_price: MoneyValue | None = None
    sale_price: MoneyValue | None = None
    item_status: str
    epc_status: str
    observation: str | None
    image_mode: str
    image_asset_id: str | None
    print_status: str
    source_file_name: str | None
    source_row_number: int | None
    lifecycle_state: str
    saved_stock_item_id: str | None
    created_at: datetime
    updated_at: datetime | None


class PreloadSessionResponse(BaseModel):
    id: str
    tenant_id: str
    store_id: str | None
    source_file_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime | None
    lines: list[PreloadLineResponse]


class PreloadLinePatchRequest(BaseModel):
    sale_price: MoneyValue | None = None
    epc: str | None = None
    pool: str | None = None
    location_code: str | None = None
    vendible: bool | None = None
    observation: str | None = None
    image_mode: Literal["existing", "replace", "add", "blank"] | None = None
    image_asset_id: UUID | None = None


class PendingEpcAssignRequest(BaseModel):
    epc: str


class EpcAssignmentHistoryResponse(BaseModel):
    epc: str
    current: dict | None
    history: list[dict]


class EpcReleaseRequest(BaseModel):
    epc: str
    item_uid: str
    reason: str


class EpcReleaseResponse(BaseModel):
    released: bool
    epc: str
    item_uid: str
    reason: str


class SkuImageUpsertRequest(BaseModel):
    asset_id: UUID
    mode: Literal["use_existing", "replace", "add", "blank"] = "add"
    file_hash: str | None = None


class SkuImageResponse(BaseModel):
    id: str
    tenant_id: str
    sku: str
    asset_id: str
    file_hash: str | None
    is_primary: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime | None


class ItemIssueRequest(BaseModel):
    issue_state: Literal["DAMAGED", "STOLEN", "DONATED", "LOST", "ADDED_BY_ERROR", "REVIEW", "WRITE_OFF_CONFIRMED"]
    release_epc: bool
    release_reason: str | None = None
    keep_epc_assigned: bool = False
    special_permission_token: str | None = None
    observation: str | None = None


class ItemIssueResolveRequest(BaseModel):
    item_status: str
    observation: str | None = None


class ItemIssueResponse(BaseModel):
    item_uid: str
    item_status: str
    issue_state: str | None
    epc_status: str


class ItemIssueResolveResponse(BaseModel):
    item_uid: str
    item_status: str
    issue_state: str | None


AiDocumentType = Literal[
    "invoice",
    "packing_list",
    "handwritten_note",
    "product_labels",
    "product_photo",
    "spreadsheet",
    "word_document",
    "mixed",
    "other",
    "unknown",
]
AiPricingMode = Literal["markup_percent", "margin_percent", "multiplier", "manual"]


class AiPreloadWarning(BaseModel):
    message: str
    severity: Literal["info", "warning", "error"] = "warning"


class AiPreloadLine(BaseModel):
    row_key: str
    sku: str | None = None
    suggested_sku: str | None = None
    description: str
    variant_1: str | None = None
    variant_2: str | None = None
    pool: str | None = None
    location_code: str | None = None
    sellable: bool = True
    quantity: int = Field(ge=1)
    original_cost: str | None = None
    source_currency: str | None = None
    exchange_rate_to_gtq: str | None = None
    cost_gtq: str | None = None
    suggested_price_gtq: str | None = None
    needs_review: bool = True
    confidence: float | None = None
    notes: str | None = None
    source_file_name: str | None = None
    source_row_number: int | None = None


class AiPreloadDocumentSummary(BaseModel):
    document_type: AiDocumentType = "unknown"
    supplier_name: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    detected_currency: str | None = None
    overall_confidence: float | None = None


class AiPreloadPricingSummary(BaseModel):
    source_currency: str = "GTQ"
    exchange_rate_to_gtq: str | None = None
    pricing_mode: AiPricingMode = "manual"
    markup_percent: str | None = None
    margin_percent: str | None = None
    multiplier: str | None = None
    rounding_step: str = "1.00"


class AiPreloadAnalyzeResponse(BaseModel):
    extraction_id: str
    store_id: str
    document_summary: AiPreloadDocumentSummary
    pricing: AiPreloadPricingSummary
    total_lines: int
    lines: list[AiPreloadLine]
    warnings: list[AiPreloadWarning]


class AiPreloadConfirmRequest(BaseModel):
    store_id: str
    extraction_id: str | None = None
    source_currency: str = "GTQ"
    exchange_rate_to_gtq: str | None = None
    pricing_mode: AiPricingMode = "manual"
    markup_percent: str | None = None
    margin_percent: str | None = None
    multiplier: str | None = None
    rounding_step: str = "1.00"
    lines: list[AiPreloadLine]


class AiPreloadConfirmResponse(BaseModel):
    preload_session_id: str
    created_lines_count: int
    review_required_count: int
    warnings: list[AiPreloadWarning]
    trace_id: str
