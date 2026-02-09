import uuid
from datetime import datetime

import pytest

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


def _stock_data(
    epc: str | None,
    status: str,
    *,
    location_code: str = "LOC-1",
    pool: str = "P1",
    location_is_vendible: bool = True,
):
    return {
        "sku": "SKU-1",
        "description": "Blue Jacket",
        "var1_value": "Blue",
        "var2_value": "L",
        "epc": epc,
        "location_code": location_code,
        "pool": pool,
        "status": status,
        "location_is_vendible": location_is_vendible,
        "image_asset_id": None,
        "image_url": None,
        "image_thumb_url": None,
        "image_source": None,
        "image_updated_at": None,
    }


def _create_stock_item(db_session, tenant, *, epc: str | None, status: str):
    item = StockItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku="SKU-1",
        description="Blue Jacket",
        var1_value="Blue",
        var2_value="L",
        epc=epc,
        location_code="LOC-1",
        pool="P1",
        status=status,
        location_is_vendible=True,
        image_asset_id=None,
        image_url=None,
        image_thumb_url=None,
        image_source=None,
        image_updated_at=None,
        created_at=datetime.utcnow(),
    )
    db_session.add(item)
    db_session.commit()
    return item


def test_write_off_success_rfid(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="write-off")
    _create_stock_item(db_session, tenant, epc="A" * 24, status="RFID")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-write-off-1",
        "action": "WRITE_OFF",
        "payload": {"reason": "DAMAGED", "qty": 1, "data": _stock_data("A" * 24, "RFID")},
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "write-off-1"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 1

    rows = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).all()
    assert rows == []
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


@pytest.mark.parametrize(
    ("action", "payload_overrides"),
    [
        ("REPRICE", {"price": 99.5, "currency": "USD"}),
        ("MARKDOWN_BY_AGE", {"policy": "age-30"}),
        ("REPRINT_LABEL", {}),
    ],
)
def test_action_audit_only_success(client, db_session, action, payload_overrides):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix=f"audit-{action.lower()}")
    item = _create_stock_item(db_session, tenant, epc="B" * 24, status="RFID")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": f"txn-{action}-1",
        "action": action,
        "payload": {"data": _stock_data("B" * 24, "RFID"), **payload_overrides},
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"{action}-1"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["processed"] == 1

    db_session.refresh(item)
    assert item.epc == "B" * 24
    assert item.status == "RFID"


def test_replace_epc_success(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="replace-epc")
    _create_stock_item(db_session, tenant, epc="C" * 24, status="RFID")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-replace-1",
        "action": "REPLACE_EPC",
        "payload": {"current_epc": "C" * 24, "new_epc": "D" * 24},
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "replace-1"},
        json=payload,
    )
    assert response.status_code == 200

    row = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).one()
    assert row.epc == "D" * 24
    assert row.status == "RFID"


@pytest.mark.parametrize("action", ["MARK_EPC_DAMAGED", "RETIRE_EPC", "RETURN_EPC_TO_POOL"])
def test_epc_lifecycle_success(client, db_session, action):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix=f"lifecycle-{action.lower()}")
    _create_stock_item(db_session, tenant, epc="E" * 24, status="RFID")
    token = _login(client, user.username, "Pass1234!")
    action_payload = {"epc": "E" * 24}
    if action == "RETURN_EPC_TO_POOL":
        action_payload["epc_type"] = "REUSABLE_TAG"
    payload = {
        "transaction_id": f"txn-{action}-1",
        "action": action,
        "payload": action_payload,
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"{action}-1"},
        json=payload,
    )
    assert response.status_code == 200
    row = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).one()
    assert row.epc is None
    assert row.status == "PENDING"

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
    assert total_rfid + total_pending == 1


def test_invalid_epc_format_action(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="invalid-epc-action")
    _create_stock_item(db_session, tenant, epc="F" * 24, status="RFID")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-invalid-epc-1",
        "action": "REPLACE_EPC",
        "payload": {"current_epc": "F" * 24, "new_epc": "not-epc"},
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "invalid-epc-action"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_duplicate_epc_replace_denied(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="dup-epc-action")
    _create_stock_item(db_session, tenant, epc="1" * 24, status="RFID")
    _create_stock_item(db_session, tenant, epc="2" * 24, status="RFID")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-dup-epc-1",
        "action": "REPLACE_EPC",
        "payload": {"current_epc": "1" * 24, "new_epc": "2" * 24},
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "dup-epc-action"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_epc_lifecycle_invalid_transition(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="invalid-lifecycle")
    _create_stock_item(db_session, tenant, epc="3" * 24, status="PENDING")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-invalid-lifecycle-1",
        "action": "RETURN_EPC_TO_POOL",
        "payload": {"epc": "3" * 24, "epc_type": "REUSABLE_TAG"},
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "invalid-lifecycle"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_non_reusable_label_cannot_return_to_pool(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="non-reusable")
    _create_stock_item(db_session, tenant, epc="4" * 24, status="RFID")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-non-reusable-1",
        "action": "RETURN_EPC_TO_POOL",
        "payload": {"epc": "4" * 24, "epc_type": "NON_REUSABLE_LABEL"},
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "non-reusable"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_write_off_lost_in_transit_denied(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="lost-transit")
    item = StockItem(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        sku="SKU-1",
        description="Blue Jacket",
        var1_value="Blue",
        var2_value="L",
        epc="5" * 24,
        location_code="IN_TRANSIT",
        pool="P1",
        status="RFID",
        location_is_vendible=False,
    )
    db_session.add(item)
    db_session.commit()
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-lost-transit-1",
        "action": "WRITE_OFF",
        "payload": {
            "reason": "LOST",
            "qty": 1,
            "data": _stock_data(
                "5" * 24,
                "RFID",
                location_code="IN_TRANSIT",
                location_is_vendible=False,
            ),
        },
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "lost-transit"},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code


def test_stock_action_tenant_boundary_denied(client, db_session):
    run_seed(db_session)
    tenant_a, user_a = _create_tenant_user(db_session, suffix="tenant-a")
    tenant_b, _user_b = _create_tenant_user(db_session, suffix="tenant-b")
    _create_stock_item(db_session, tenant_b, epc="6" * 24, status="RFID")
    token = _login(client, user_a.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-tenant-boundary-1",
        "tenant_id": str(tenant_b.id),
        "action": "REPLACE_EPC",
        "payload": {"current_epc": "6" * 24, "new_epc": "7" * 24},
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tenant-boundary"},
        json=payload,
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.CROSS_TENANT_ACCESS_DENIED.code


def test_stock_action_rbac_denied(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="rbac", role="USER")
    _create_stock_item(db_session, tenant, epc="8" * 24, status="RFID")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-rbac-1",
        "action": "REPRINT_LABEL",
        "payload": {"data": _stock_data("8" * 24, "RFID")},
    }

    response = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "rbac"},
        json=payload,
    )
    assert response.status_code == 403
    assert response.json()["code"] == ErrorCatalog.PERMISSION_DENIED.code


def test_stock_action_idempotency_replay_and_conflict(client, db_session):
    run_seed(db_session)
    tenant, user = _create_tenant_user(db_session, suffix="idempotency")
    _create_stock_item(db_session, tenant, epc="9" * 24, status="RFID")
    token = _login(client, user.username, "Pass1234!")
    payload = {
        "transaction_id": "txn-idempotency-1",
        "action": "REPRINT_LABEL",
        "payload": {"data": _stock_data("9" * 24, "RFID")},
    }

    first = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-1"},
        json=payload,
    )
    assert first.status_code == 200

    replay = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-1"},
        json=payload,
    )
    assert replay.status_code == 200
    assert replay.headers.get("X-Idempotency-Result") == ErrorCatalog.IDEMPOTENCY_REPLAY.code

    conflict_payload = {
        "transaction_id": "txn-idempotency-2",
        "action": "REPRINT_LABEL",
        "payload": {"data": _stock_data("9" * 24, "RFID", pool="P2")},
    }
    conflict = client.post(
        "/aris3/stock/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem-1"},
        json=conflict_payload,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code
