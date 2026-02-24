import uuid
from datetime import datetime
from decimal import Decimal

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_user(db_session, *, suffix: str, role: str = "ADMIN"):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=f"user-{suffix}",
        email=f"user-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role=role,
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, store, user])
    db_session.commit()
    return tenant, user


def _stock_line(epc: str | None, status: str, qty: int = 1, **prices):
    line = {
        "sku": "SKU-1",
        "description": "Blue Jacket",
        "var1_value": "Blue",
        "var2_value": "L",
        "epc": epc,
        "location_code": "LOC-1",
        "pool": "P1",
        "status": status,
        "location_is_vendible": True,
        "image_asset_id": str(uuid.uuid4()),
        "image_url": "https://example.com/image.png",
        "image_thumb_url": "https://example.com/thumb.png",
        "image_source": "catalog",
        "image_updated_at": datetime.utcnow().isoformat(),
        "qty": qty,
    }
    line.update(prices)
    return line


def test_import_epc_success(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="import-epc")
    token = _login(client, user.username, "Pass1234!")
    epc = "A" * 24
    payload = {
        "transaction_id": "txn-epc-1",
        "lines": [_stock_line(epc, status="RFID", qty=1)],
    }

    response = client.post(
        "/aris3/stock/import-epc",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "epc-1"},
        json=payload,
    )
    assert response.status_code == 201
    assert response.json()["processed"] == 1

    rows = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).all()
    assert len(rows) == 1
    assert rows[0].status == "RFID"
    total_rfid = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "RFID")
        .count()
    )
    total_pending = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "PENDING")
        .count()
    )
    assert total_rfid + total_pending == len(rows)


def test_import_sku_success(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="import-sku")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-sku-1",
        "lines": [_stock_line(None, status="PENDING", qty=2)],
    }

    response = client.post(
        "/aris3/stock/import-sku",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "sku-1"},
        json=payload,
    )
    assert response.status_code == 201
    assert response.json()["processed"] == 2

    rows = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).all()
    assert len(rows) == 2
    assert {row.status for row in rows} == {"PENDING"}
    total_rfid = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "RFID")
        .count()
    )
    total_pending = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "PENDING")
        .count()
    )
    assert total_rfid + total_pending == len(rows)


def test_invalid_epc_format(client, db_session):
    run_seed(db_session)
    _tenant, user = _create_tenant_user(db_session, suffix="invalid-epc")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-epc-2",
        "lines": [_stock_line("a" * 24, status="RFID", qty=1)],
    }

    response = client.post(
        "/aris3/stock/import-epc",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "epc-2"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_duplicate_epc_same_tenant(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="dup-epc")
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            sku="SKU-1",
            description="Blue Jacket",
            var1_value="Blue",
            var2_value="L",
            epc="B" * 24,
            location_code="LOC-1",
            pool="P1",
            status="RFID",
            location_is_vendible=True,
        )
    )
    db_session.commit()
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-epc-3",
        "lines": [_stock_line("B" * 24, status="RFID", qty=1)],
    }

    response = client.post(
        "/aris3/stock/import-epc",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "epc-3"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_migrate_success_total_unchanged(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="migrate-success")
    pending_item = StockItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku="SKU-1",
        description="Blue Jacket",
        var1_value="Blue",
        var2_value="L",
        epc=None,
        location_code="LOC-1",
        pool="P1",
        status="PENDING",
        location_is_vendible=True,
    )
    db_session.add(pending_item)
    db_session.commit()
    before_pending = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "PENDING")
        .count()
    )
    before_rfid = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "RFID")
        .count()
    )
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-migrate-1",
        "epc": "C" * 24,
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

    response = client.post(
        "/aris3/stock/migrate-sku-to-epc",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "migrate-1"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["migrated"] == 1

    rows = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).all()
    assert len(rows) == 1
    assert rows[0].status == "RFID"
    assert rows[0].epc == "C" * 24
    after_pending = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "PENDING")
        .count()
    )
    after_rfid = (
        db_session.query(StockItem)
        .filter(StockItem.tenant_id == tenant.id, StockItem.status == "RFID")
        .count()
    )
    assert before_pending - 1 == after_pending
    assert before_rfid + 1 == after_rfid
    assert before_pending + before_rfid == after_pending + after_rfid


def test_migrate_failure_when_pending_zero(client, db_session):
    run_seed(db_session)
    _tenant, user = _create_tenant_user(db_session, suffix="migrate-fail")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-migrate-2",
        "epc": "D" * 24,
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

    response = client.post(
        "/aris3/stock/migrate-sku-to-epc",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "migrate-2"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_tenant_boundary_enforcement(client, db_session):
    run_seed(db_session)
    tenant_a, user_a = _create_tenant_user(db_session, suffix="tenant-a")
    tenant_b, _user_b = _create_tenant_user(db_session, suffix="tenant-b")
    token = _login(client, user_a.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-tenant-1",
        "tenant_id": str(tenant_b.id),
        "lines": [_stock_line("E" * 24, status="RFID", qty=1)],
    }

    response = client.post(
        "/aris3/stock/import-epc",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tenant-1"},
        json=payload,
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.CROSS_TENANT_ACCESS_DENIED.code
    assert db_session.query(StockItem).filter(StockItem.tenant_id == tenant_a.id).count() == 0


def test_idempotency_replay_and_conflict_import_epc(client, db_session):
    run_seed(db_session)
    _tenant, user = _create_tenant_user(db_session, suffix="idemp-epc")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-idemp-epc-1",
        "lines": [_stock_line("F" * 24, status="RFID", qty=1)],
    }
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idemp-epc-1"}

    first = client.post("/aris3/stock/import-epc", headers=headers, json=payload)
    assert first.status_code == 201
    replay = client.post("/aris3/stock/import-epc", headers=headers, json=payload)
    assert replay.status_code == 201
    assert replay.headers["X-Idempotency-Result"] == ErrorCatalog.IDEMPOTENCY_REPLAY.code

    conflict_payload = {
        "transaction_id": "txn-idemp-epc-2",
        "lines": [_stock_line("1" * 24, status="RFID", qty=1)],
    }
    conflict = client.post("/aris3/stock/import-epc", headers=headers, json=conflict_payload)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code


def test_idempotency_replay_and_conflict_import_sku(client, db_session):
    run_seed(db_session)
    _tenant, user = _create_tenant_user(db_session, suffix="idemp-sku")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-idemp-sku-1",
        "lines": [_stock_line(None, status="PENDING", qty=1)],
    }
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idemp-sku-1"}

    first = client.post("/aris3/stock/import-sku", headers=headers, json=payload)
    assert first.status_code == 201
    replay = client.post("/aris3/stock/import-sku", headers=headers, json=payload)
    assert replay.status_code == 201
    assert replay.headers["X-Idempotency-Result"] == ErrorCatalog.IDEMPOTENCY_REPLAY.code

    conflict_payload = {
        "transaction_id": "txn-idemp-sku-2",
        "lines": [_stock_line(None, status="PENDING", qty=2)],
    }
    conflict = client.post("/aris3/stock/import-sku", headers=headers, json=conflict_payload)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code


def test_idempotency_replay_and_conflict_migrate(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="idemp-migrate")
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            sku="SKU-1",
            description="Blue Jacket",
            var1_value="Blue",
            var2_value="L",
            epc=None,
            location_code="LOC-1",
            pool="P1",
            status="PENDING",
            location_is_vendible=True,
        )
    )
    db_session.commit()
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-idemp-migrate-1",
        "epc": "9" * 24,
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
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idemp-migrate-1"}

    first = client.post("/aris3/stock/migrate-sku-to-epc", headers=headers, json=payload)
    assert first.status_code == 200
    replay = client.post("/aris3/stock/migrate-sku-to-epc", headers=headers, json=payload)
    assert replay.status_code == 200
    assert replay.headers["X-Idempotency-Result"] == ErrorCatalog.IDEMPOTENCY_REPLAY.code

    conflict_payload = {
        "transaction_id": "txn-idemp-migrate-2",
        "epc": "8" * 24,
        "data": payload["data"],
    }
    conflict = client.post("/aris3/stock/migrate-sku-to-epc", headers=headers, json=conflict_payload)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code


def test_import_sku_with_prices_persists_and_lists(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="sku-prices")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-sku-prices-1",
        "lines": [
            _stock_line(
                None,
                status="PENDING",
                qty=1,
                cost_price="12.30",
                suggested_price="19.99",
                sale_price="17.50",
            )
        ],
    }

    response = client.post(
        "/aris3/stock/import-sku",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "sku-prices-1"},
        json=payload,
    )
    assert response.status_code == 201

    row = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).one()
    assert row.cost_price == Decimal("12.30")
    assert row.suggested_price == Decimal("19.99")
    assert row.sale_price == Decimal("17.50")

    stock_response = client.get("/aris3/stock", headers={"Authorization": f"Bearer {token}"})
    assert stock_response.status_code == 200
    stock_row = stock_response.json()["rows"][0]
    assert stock_row["cost_price"] == "12.30"
    assert stock_row["suggested_price"] == "19.99"
    assert stock_row["sale_price"] == "17.50"


def test_import_sku_without_prices_keeps_null_prices(client, db_session):
    run_seed(db_session)
    _tenant, user = _create_tenant_user(db_session, suffix="sku-no-prices")
    token = _login(client, user.username, "Pass1234!")
    payload = {"transaction_id": "txn-sku-no-prices-1", "lines": [_stock_line(None, status="PENDING", qty=1)]}

    response = client.post(
        "/aris3/stock/import-sku",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "sku-no-prices-1"},
        json=payload,
    )
    assert response.status_code == 201

    stock_response = client.get("/aris3/stock", headers={"Authorization": f"Bearer {token}"})
    row = stock_response.json()["rows"][0]
    assert row["cost_price"] is None
    assert row["suggested_price"] is None
    assert row["sale_price"] is None


def test_import_epc_with_prices_persists_and_lists(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="epc-prices")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-epc-prices-1",
        "lines": [
            _stock_line(
                "ABCDEFABCDEFABCDEFABCDEF",
                status="RFID",
                qty=1,
                cost_price="20.00",
                suggested_price="30.00",
                sale_price="27.00",
            )
        ],
    }

    response = client.post(
        "/aris3/stock/import-epc",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "epc-prices-1"},
        json=payload,
    )
    assert response.status_code == 201

    row = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).one()
    assert row.cost_price == Decimal("20.00")
    assert row.suggested_price == Decimal("30.00")
    assert row.sale_price == Decimal("27.00")

    stock_response = client.get("/aris3/stock", headers={"Authorization": f"Bearer {token}"})
    stock_row = stock_response.json()["rows"][0]
    assert stock_row["cost_price"] == "20.00"


def test_migrate_sku_to_epc_prices_override_or_inherit(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="migrate-prices")
    token = _login(client, user.username, "Pass1234!")

    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            sku="SKU-1",
            description="Blue Jacket",
            var1_value="Blue",
            var2_value="L",
            epc=None,
            location_code="LOC-1",
            pool="P1",
            status="PENDING",
            location_is_vendible=True,
            cost_price=Decimal("10.00"),
            suggested_price=Decimal("15.00"),
            sale_price=Decimal("13.00"),
        )
    )
    db_session.commit()

    base_data = {
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
    }

    inherit = client.post(
        "/aris3/stock/migrate-sku-to-epc",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "migrate-prices-1"},
        json={"transaction_id": "txn-migrate-prices-1", "epc": "1" * 24, "data": base_data},
    )
    assert inherit.status_code == 200
    inherited_row = db_session.query(StockItem).filter(StockItem.epc == "1" * 24).one()
    assert inherited_row.cost_price == Decimal("10.00")

    inherited_row.epc = None
    inherited_row.status = "PENDING"
    db_session.commit()

    explicit_data = {**base_data, "cost_price": "11.00", "suggested_price": "16.00", "sale_price": "14.00"}
    explicit = client.post(
        "/aris3/stock/migrate-sku-to-epc",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "migrate-prices-2"},
        json={"transaction_id": "txn-migrate-prices-2", "epc": "2" * 24, "data": explicit_data},
    )
    assert explicit.status_code == 200
    explicit_row = db_session.query(StockItem).filter(StockItem.epc == "2" * 24).one()
    assert explicit_row.cost_price == Decimal("11.00")
    assert explicit_row.suggested_price == Decimal("16.00")
    assert explicit_row.sale_price == Decimal("14.00")


def test_negative_price_validation(client, db_session):
    run_seed(db_session)
    _tenant, user = _create_tenant_user(db_session, suffix="negative-prices")
    token = _login(client, user.username, "Pass1234!")

    response = client.post(
        "/aris3/stock/import-sku",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "negative-prices-1"},
        json={
            "transaction_id": "txn-negative-prices-1",
            "lines": [_stock_line(None, status="PENDING", qty=1, cost_price="-1.00")],
        },
    )
    assert response.status_code == 422


def test_price_validation_rejects_more_than_two_decimals(client, db_session):
    run_seed(db_session)
    _tenant, user = _create_tenant_user(db_session, suffix="price-scale")
    token = _login(client, user.username, "Pass1234!")

    response = client.post(
        "/aris3/stock/import-sku",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "price-scale-1"},
        json={
            "transaction_id": "txn-price-scale-1",
            "lines": [_stock_line(None, status="PENDING", qty=1, cost_price="12.345")],
        },
    )

    assert response.status_code == 422
