from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aris3_client_sdk.exceptions import ApiError
from aris3_client_sdk.models_stock import (
    StockDataBlock,
    StockImportResponse,
    StockMeta,
    StockMigrateResponse,
    StockQuery,
    StockRow,
    StockTableResponse,
    StockTotals,
)

from services.permissions_service import PermissionGate
from services.stock_service import StockService
from ui.stock.import_epc_view import ImportEpcView
from ui.stock.import_sku_view import ImportSkuView
from ui.stock.migrate_sku_to_epc_view import MigrateSkuToEpcView
from ui.stock.stock_filters_panel import StockFiltersPanel
from ui.stock.stock_list_view import StockListView


@dataclass
class FakeStockClient:
    table_response: StockTableResponse
    import_response: StockImportResponse = field(
        default_factory=lambda: StockImportResponse(processed=1, trace_id="trace-import")
    )
    migrate_response: StockMigrateResponse = field(
        default_factory=lambda: StockMigrateResponse(migrated=1, trace_id="trace-migrate")
    )
    last_filters: dict[str, Any] | None = None
    last_import_epc: dict[str, Any] | None = None
    last_import_sku: dict[str, Any] | None = None
    last_migrate: dict[str, Any] | None = None
    fail_get: Exception | None = None

    def get_stock(self, filters: StockQuery) -> StockTableResponse:
        if self.fail_get:
            raise self.fail_get
        self.last_filters = filters.model_dump(by_alias=True, exclude_none=True, mode="json")
        return self.table_response

    def import_epc(self, lines: list[dict[str, Any]], transaction_id: str, idempotency_key: str) -> StockImportResponse:
        self.last_import_epc = {
            "lines": lines,
            "transaction_id": transaction_id,
            "idempotency_key": idempotency_key,
        }
        from aris3_client_sdk.stock_validation import validate_import_epc_line

        for idx, line in enumerate(lines):
            validate_import_epc_line(line, idx)
        return self.import_response

    def import_sku(self, lines: list[dict[str, Any]], transaction_id: str, idempotency_key: str) -> StockImportResponse:
        self.last_import_sku = {
            "lines": lines,
            "transaction_id": transaction_id,
            "idempotency_key": idempotency_key,
        }
        from aris3_client_sdk.stock_validation import validate_import_sku_line

        for idx, line in enumerate(lines):
            validate_import_sku_line(line, idx)
        return self.import_response

    def migrate_sku_to_epc(
        self, lines: list[dict[str, Any]], transaction_id: str, idempotency_key: str
    ) -> StockMigrateResponse:
        self.last_migrate = {
            "lines": lines,
            "transaction_id": transaction_id,
            "idempotency_key": idempotency_key,
        }
        return self.migrate_response


class FakeSession:
    def __init__(self, stock_client: FakeStockClient) -> None:
        self._stock_client = stock_client

    def stock_client(self) -> FakeStockClient:
        return self._stock_client


def _stock_response() -> StockTableResponse:
    return StockTableResponse(
        meta=StockMeta(page=1, page_size=50, sort_by="sku", sort_dir="asc"),
        rows=[
            StockRow(
                sku="SKU-1",
                description="Item",
                var1_value="BLUE",
                var2_value="42",
                epc="ABCDEFABCDEFABCDEFABCDEF",
                location_code="SELL-1",
                pool="RFID",
                status="RFID",
            )
        ],
        totals=StockTotals(total_rfid=10, total_pending=5, total_units=15, total_rows=1),
        trace_id="trace-stock",
    )


def _allow_all_gate() -> PermissionGate:
    return PermissionGate(
        [
            {"key": "stock.view", "allowed": True},
            {"key": "stock.import_epc", "allowed": True},
            {"key": "stock.import_sku", "allowed": True},
            {"key": "stock.migrate_sku_to_epc", "allowed": True},
        ]
    )


def _base_line(**overrides: Any) -> dict[str, Any]:
    line = {
        "sku": "SKU-1",
        "description": "Item",
        "var1_value": "BLUE",
        "var2_value": "42",
        "location_code": "SELL-1",
        "pool": "RFID",
        "status": "RFID",
        "qty": 1,
        "epc": "ABCDEFABCDEFABCDEFABCDEF",
    }
    line.update(overrides)
    return line


def test_stock_list_loads_meta_rows_totals() -> None:
    session = FakeSession(FakeStockClient(table_response=_stock_response()))
    list_view = StockListView(service=StockService(session=session), gate=_allow_all_gate())  # type: ignore[arg-type]

    ok = list_view.load(StockFiltersPanel(sku="SKU-1").as_query())

    rendered = list_view.render()
    assert ok is True
    assert rendered["meta"]["page"] == 1
    assert rendered["table"]["count"] == 1
    assert rendered["totals"]["rfid"] == 10


def test_filters_passed_to_sdk_query() -> None:
    client = FakeStockClient(table_response=_stock_response())
    session = FakeSession(client)
    list_view = StockListView(service=StockService(session=session), gate=_allow_all_gate())  # type: ignore[arg-type]
    filters = StockFiltersPanel(q="shoe", sku="SKU-1", pool="RFID", page=2, page_size=25, sort_by="sku", sort_dir="desc")

    list_view.load(filters.as_query())

    assert client.last_filters is not None
    assert client.last_filters["q"] == "shoe"
    assert client.last_filters["sku"] == "SKU-1"
    assert client.last_filters["pool"] == "RFID"
    assert client.last_filters["page"] == 2
    assert client.last_filters["sort_dir"] == "desc"


def test_import_epc_validation_blocks_invalid_epc_and_qty() -> None:
    session = FakeSession(FakeStockClient(table_response=_stock_response()))
    service = StockService(session=session)  # type: ignore[arg-type]
    list_view = StockListView(service=service, gate=_allow_all_gate())
    view = ImportEpcView(service=service, list_view=list_view)

    result = view.submit([_base_line(epc="invalid", qty=2)])

    assert result["ok"] is False
    assert "epc" in result["error"] or "qty" in result["error"]


def test_import_sku_validation_blocks_invalid_qty_and_required_fields() -> None:
    session = FakeSession(FakeStockClient(table_response=_stock_response()))
    service = StockService(session=session)  # type: ignore[arg-type]
    list_view = StockListView(service=service, gate=_allow_all_gate())
    view = ImportSkuView(service=service, list_view=list_view)

    result = view.submit([_base_line(status="PENDING", epc=None, qty=0, sku=None)])

    assert result["ok"] is False
    assert "qty" in result["error"] or "sku" in result["error"]


def test_migrate_flow_sends_payload_and_idempotency_metadata() -> None:
    client = FakeStockClient(table_response=_stock_response())
    session = FakeSession(client)
    service = StockService(session=session)  # type: ignore[arg-type]
    list_view = StockListView(service=service, gate=_allow_all_gate())
    view = MigrateSkuToEpcView(service=service, list_view=list_view)
    payload = {
        "epc": "ABCDEFABCDEFABCDEFABCDEF",
        "data": StockDataBlock(
            sku="SKU-1",
            description="Item",
            var1_value="BLUE",
            var2_value="42",
            location_code="SELL-1",
            pool="PENDING",
            status="PENDING",
        ).model_dump(mode="json", exclude_none=True),
    }

    result = view.submit(payload)

    assert result["ok"] is True
    assert result["expected_effect"] == "PENDING -1, RFID +1, TOTAL unchanged"
    assert client.last_migrate is not None
    assert client.last_migrate["lines"][0].epc == payload["epc"]
    assert client.last_migrate["transaction_id"]
    assert client.last_migrate["idempotency_key"]


def test_permission_gating_hides_unauthorized_actions() -> None:
    session = FakeSession(FakeStockClient(table_response=_stock_response()))
    gate = PermissionGate([{"key": "stock.view", "allowed": True}])
    list_view = StockListView(service=StockService(session=session), gate=gate)  # type: ignore[arg-type]

    rendered = list_view.render()

    assert rendered["can_view"] is True
    assert rendered["actions"]["import_epc"] is False
    assert rendered["actions"]["import_sku"] is False
    assert rendered["actions"]["migrate_sku_to_epc"] is False


def test_service_error_mapping_surfaces_user_friendly_message() -> None:
    api_error = ApiError(
        code="STOCK_FORBIDDEN",
        message="Permission denied",
        details="tenant mismatch",
        trace_id="trace-denied",
        status_code=403,
    )
    client = FakeStockClient(table_response=_stock_response(), fail_get=api_error)
    session = FakeSession(client)
    list_view = StockListView(service=StockService(session=session), gate=_allow_all_gate())  # type: ignore[arg-type]

    ok = list_view.load({})

    rendered = list_view.render()
    assert ok is False
    assert rendered["error"] == "Permission denied"
    assert rendered["trace_id"] == "trace-denied"
