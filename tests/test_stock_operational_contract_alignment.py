import uuid

import pytest

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed
from tests.pos_sales_helpers import sale_line, sale_payload


def _login(client, username: str, password: str = "Pass1234!") -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _bootstrap(db_session, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store_a = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store A {suffix}")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store B {suffix}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store_a.id,
        username=f"admin-{suffix}",
        email=f"admin-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, store_a, store_b, user])
    db_session.commit()
    return tenant, store_a, store_b, user


def _add_stock(db_session, *, tenant_id, store_id, sku, status, epc=None, vendible=True, location_code="LOC-1", pool="SALE"):
    row = StockItem(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        store_id=store_id,
        sku=sku,
        description="Item",
        var1_value="V1",
        var2_value="V2",
        epc=epc,
        location_code=location_code,
        pool=pool,
        status=status,
        location_is_vendible=vendible,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_stock_store_scope_and_history_modes(client, db_session):
    run_seed(db_session)
    tenant, store_a, store_b, user = _bootstrap(db_session, "stock-scope")
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_a.id, sku="SKU-A", status="PENDING", epc=None)
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_b.id, sku="SKU-B", status="PENDING", epc=None)
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_a.id, sku="SKU-SOLD", status="SOLD", epc="SOLD" + "1" * 20)

    token = _login(client, user.username)

    scoped = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id)},
    )
    assert scoped.status_code == 200
    rows = scoped.json()["rows"]
    assert rows
    assert {row["store_id"] for row in rows} == {str(store_a.id)}
    assert all(row["status"] != "SOLD" for row in rows)
    assert all(
        row["store_id"] == str(store_a.id)
        for row in rows
    )

    history = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id), "view": "history"},
    )
    assert history.status_code == 200
    history_rows = history.json()["rows"]
    assert len(history_rows) == 1
    assert history_rows[0]["status"] == "SOLD"
    assert history_rows[0]["is_historical"] is True
    assert history_rows[0]["available_for_sale"] is False
    assert history_rows[0]["available_for_transfer"] is False


def test_stock_operational_view_is_strictly_scoped_to_requested_store(client, db_session):
    run_seed(db_session)
    tenant, store_a, store_b, user = _bootstrap(db_session, "operational-store-scope")
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_a.id, sku="SKU-SCOPE-A", status="PENDING", epc=None, vendible=True)
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_b.id, sku="SKU-SCOPE-B", status="PENDING", epc=None, vendible=True)

    token = _login(client, user.username)
    scoped = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "store_id": str(store_a.id),
            "view": "operational",
            "include_sold": "false",
            "page": 1,
            "page_size": 50,
            "sort_by": "created_at",
            "sort_dir": "desc",
        },
    )
    assert scoped.status_code == 200
    rows = scoped.json()["rows"]
    assert rows
    assert all(row["store_id"] == str(store_a.id) for row in rows)


@pytest.mark.parametrize(
    ("params", "expected_statuses"),
    [
        ({"include_sold": "false"}, {"PENDING"}),
        ({"include_sold": "true"}, {"PENDING", "SOLD"}),
        ({"view": "all"}, {"PENDING", "SOLD"}),
        ({"view": "history"}, {"SOLD"}),
    ],
)
def test_stock_store_scope_has_no_cross_store_leaks_in_all_read_modes(client, db_session, params, expected_statuses):
    run_seed(db_session)
    tenant, store_a, store_b, user = _bootstrap(db_session, "all-read-modes-store-scope")
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_a.id, sku="SKU-SCOPE-TARGET", status="PENDING", epc=None, vendible=True)
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_a.id, sku="SKU-SCOPE-TARGET-SOLD", status="SOLD", epc="SOLD" + "2" * 20, vendible=True)
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_b.id, sku="SKU-SCOPE-LEAK", status="PENDING", epc=None, vendible=True)
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_b.id, sku="SKU-SCOPE-LEAK-SOLD", status="SOLD", epc="SOLD" + "3" * 20, vendible=True)

    token = _login(client, user.username)
    response = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "store_id": str(store_a.id),
            "page": 1,
            "page_size": 50,
            "sort_by": "created_at",
            "sort_dir": "desc",
            **params,
        },
    )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert rows
    assert all(row["store_id"] == str(store_a.id) for row in rows)
    assert "SKU-SCOPE-LEAK" not in {row["sku"] for row in rows}
    assert set(row["status"] for row in rows).issubset(expected_statuses)

    if params.get("view") != "history":
        sample = rows[0]
        assert "available_for_sale" in sample
        assert "available_for_transfer" in sample
        assert "sale_mode" in sample
        assert "transfer_mode" in sample
        assert "available_qty" in sample


def test_unsold_rfid_without_epc_is_sale_and_transfer_capable(client, db_session):
    run_seed(db_session)
    tenant, store_a, _, user = _bootstrap(db_session, "rfid-no-epc")
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_a.id, sku="SKU-RFID", status="RFID", epc=None, vendible=True)

    token = _login(client, user.username)
    response = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id)},
    )
    assert response.status_code == 200
    row = response.json()["rows"][0]
    assert row["status"] == "RFID"
    assert row["epc"] is None
    assert row["available_for_sale"] is True
    assert row["available_for_transfer"] is True
    assert row["sale_mode"] == "SKU"
    assert row["transfer_mode"] == "SKU"


def test_available_for_sale_rows_can_be_sold(client, db_session):
    run_seed(db_session)
    tenant, store_a, _, user = _bootstrap(db_session, "sale-alignment")
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_a.id, sku="SKU-SALE", status="PENDING", epc=None, vendible=True)

    token = _login(client, user.username)
    stock = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id), "sku": "SKU-SALE"},
    )
    assert stock.status_code == 200
    row = stock.json()["rows"][0]
    assert row["available_for_sale"] is True
    assert row["sale_mode"] == "SKU"

    create_sale = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "sale-alignment-1"},
        json=sale_payload(
            str(store_a.id),
            [sale_line(line_type="SKU", qty=1, unit_price=None, sku="SKU-SALE", epc=None, status="PENDING")],
            transaction_id="sale-alignment-1",
        ),
    )
    assert create_sale.status_code == 201


def test_available_for_transfer_rows_can_be_used_in_transfer(client, db_session):
    run_seed(db_session)
    tenant, store_a, store_b, user = _bootstrap(db_session, "transfer-alignment")
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_a.id, sku="SKU-MOVE", status="PENDING", epc=None, vendible=True)

    token = _login(client, user.username)
    stock = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id), "sku": "SKU-MOVE"},
    )
    assert stock.status_code == 200
    row = stock.json()["rows"][0]
    assert row["available_for_transfer"] is True
    assert row["transfer_mode"] == "SKU"

    transfer = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-alignment-1"},
        json={
            "transaction_id": "transfer-alignment-1",
            "origin_store_id": str(store_a.id),
            "destination_store_id": str(store_b.id),
            "lines": [
                {
                    "line_type": "SKU",
                    "qty": 1,
                    "snapshot": {
                        "sku": "SKU-MOVE",
                        "description": "mismatch-description-allowed",
                        "var1_value": None,
                        "var2_value": None,
                        "epc": None,
                        "location_code": "LOC-1",
                        "pool": "SALE",
                        "status": "PENDING",
                        "location_is_vendible": True,
                        "image_asset_id": None,
                        "image_url": None,
                        "image_thumb_url": None,
                        "image_source": None,
                        "image_updated_at": None,
                    },
                }
            ],
        },
    )
    assert transfer.status_code == 201


def test_transfer_allows_rfid_without_epc_when_stock_reports_transferable(client, db_session):
    run_seed(db_session)
    tenant, store_a, store_b, user = _bootstrap(db_session, "transfer-rfid-no-epc")
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_a.id, sku="SKU-RFID-MOVE", status="RFID", epc=None, vendible=True)

    token = _login(client, user.username)
    stock = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id), "sku": "SKU-RFID-MOVE"},
    )
    assert stock.status_code == 200
    row = stock.json()["rows"][0]
    assert row["available_for_transfer"] is True
    assert row["transfer_mode"] == "SKU"
    assert row["sale_mode"] == "SKU"

    transfer = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "transfer-rfid-no-epc-1"},
        json={
            "transaction_id": "transfer-rfid-no-epc-1",
            "origin_store_id": str(store_a.id),
            "destination_store_id": str(store_b.id),
            "lines": [
                {
                    "line_type": "SKU",
                    "qty": 1,
                    "snapshot": {
                        "sku": "SKU-RFID-MOVE",
                        "description": "rfid-no-epc",
                        "var1_value": None,
                        "var2_value": None,
                        "epc": None,
                        "location_code": "LOC-1",
                        "pool": "SALE",
                        "status": "RFID",
                        "location_is_vendible": True,
                        "image_asset_id": None,
                        "image_url": None,
                        "image_thumb_url": None,
                        "image_source": None,
                        "image_updated_at": None,
                    },
                }
            ],
        },
    )
    assert transfer.status_code == 201


def test_jalapa_and_jutiapa_operational_rows_are_sale_and_transfer_capable(client, db_session):
    run_seed(db_session)
    tenant, jalapa_store, jutiapa_store, user = _bootstrap(db_session, "jalapa-jutiapa")
    for sku in ("SKU-POST-D-CHECK-02", "SKU-POST-C", "SKU-POST-B", "SKU-SMOKE-C"):
        _add_stock(
            db_session,
            tenant_id=tenant.id,
            store_id=jalapa_store.id,
            sku=sku,
            status="RFID",
            epc=None,
            vendible=False,
            location_code="BACK",
            pool="STOCKROOM",
        )
    _add_stock(
        db_session,
        tenant_id=tenant.id,
        store_id=jutiapa_store.id,
        sku="SKU-JUTIAPA-OK",
        status="PENDING",
        epc=None,
        vendible=True,
        location_code="LOC-1",
        pool="SALE",
    )

    token = _login(client, user.username)

    jalapa_stock = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(jalapa_store.id), "view": "operational", "scope": "self"},
    )
    assert jalapa_stock.status_code == 200
    jalapa_rows = jalapa_stock.json()["rows"]
    assert len(jalapa_rows) == 4
    for row in jalapa_rows:
        assert row["available_for_sale"] is True
        assert row["available_for_transfer"] is True
        assert row["sale_mode"] == "SKU"
        assert row["transfer_mode"] == "SKU"
        assert row["available_qty"] > 0

    jutiapa_stock = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(jutiapa_store.id), "scope": "tenant", "view": "operational", "sku": "SKU-JUTIAPA-OK"},
    )
    assert jutiapa_stock.status_code == 200
    jutiapa_row = jutiapa_stock.json()["rows"][0]
    assert jutiapa_row["store_id"] == str(jutiapa_store.id)
    assert jutiapa_row["available_for_sale"] is True
    assert jutiapa_row["available_for_transfer"] is True
    assert jutiapa_row["sale_mode"] == "SKU"
    assert jutiapa_row["transfer_mode"] == "SKU"
    assert jutiapa_row["available_qty"] > 0


def test_history_rows_remain_non_operational_with_none_modes(client, db_session):
    run_seed(db_session)
    tenant, store_a, _, user = _bootstrap(db_session, "history-non-operational")
    _add_stock(db_session, tenant_id=tenant.id, store_id=store_a.id, sku="SKU-SOLD-HISTORY", status="SOLD", epc=None, vendible=False)

    token = _login(client, user.username)
    history = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id), "view": "history"},
    )
    assert history.status_code == 200
    row = history.json()["rows"][0]
    assert row["available_for_sale"] is False
    assert row["available_for_transfer"] is False
    assert row["sale_mode"] == "NONE"
    assert row["transfer_mode"] == "NONE"


def test_unsold_operational_row_marked_saleable_can_be_sold(client, db_session):
    run_seed(db_session)
    tenant, store_a, _, user = _bootstrap(db_session, "operational-sale-validator")
    _add_stock(
        db_session,
        tenant_id=tenant.id,
        store_id=store_a.id,
        sku="SKU-POST-C",
        status="RFID",
        epc=None,
        vendible=False,
        location_code="BACK",
        pool="STOCKROOM",
    )

    token = _login(client, user.username)
    stock = client.get(
        "/aris3/stock",
        headers={"Authorization": f"Bearer {token}"},
        params={"store_id": str(store_a.id), "sku": "SKU-POST-C", "view": "operational"},
    )
    assert stock.status_code == 200
    row = stock.json()["rows"][0]
    assert row["available_for_sale"] is True
    assert row["sale_mode"] == "SKU"

    create_sale = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "sale-operational-stock-1"},
        json=sale_payload(
            str(store_a.id),
            [
                {
                    "line_type": "SKU",
                    "qty": 1,
                    "sku": "SKU-POST-C",
                    "snapshot": {
                        "sku": "SKU-POST-C",
                        "location_code": "BACK",
                        "pool": "STOCKROOM",
                        "status": "RFID",
                        "location_is_vendible": False,
                    },
                }
            ],
            transaction_id="sale-operational-stock-1",
        ),
    )
    assert create_sale.status_code == 201
