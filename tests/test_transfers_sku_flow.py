import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_context(db_session, *, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    origin_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Origin {suffix}")
    destination_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Destination {suffix}")
    origin_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=origin_store.id,
        username=f"origin-sku-{suffix}",
        email=f"origin-sku-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    destination_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=destination_store.id,
        username=f"destination-sku-{suffix}",
        email=f"destination-sku-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, origin_store, destination_store, origin_user, destination_user])
    db_session.commit()
    return tenant, origin_store, destination_store, origin_user, destination_user


def _seed_stock(db_session, *, tenant_id, store_id, epc: str, sku_qty: int):
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            store_id=store_id,
            sku="SKU-1",
            description="Transfer test item",
            var1_value="Blue",
            var2_value="L",
            epc=epc,
            location_code="LOC-1",
            pool="P1",
            status="RFID",
            location_is_vendible=True,
        )
    )
    for _ in range(sku_qty):
        db_session.add(
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                store_id=store_id,
                sku="SKU-1",
                description="Transfer test item",
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


def _line_snapshot(epc: str | None, status: str):
    return {
        "sku": "SKU-1",
        "description": "Transfer test item",
        "var1_value": "Blue",
        "var2_value": "L",
        "epc": epc,
        "location_code": "LOC-1",
        "pool": "P1",
        "status": status,
        "location_is_vendible": True,
        "image_asset_id": None,
        "image_url": None,
        "image_thumb_url": None,
        "image_source": None,
        "image_updated_at": None,
    }


def test_transfer_sku_dispatch_and_receive(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, origin_user, destination_user = _create_context(db_session, suffix="sku-ok")
    origin_token = _login(client, origin_user.username, "Pass1234!")
    destination_token = _login(client, destination_user.username, "Pass1234!")
    _seed_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc="1" * 24, sku_qty=3)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "sku-create-1"},
        json={
            "transaction_id": "txn-sku-create-1",
            "origin_store_id": str(origin.id),
            "destination_store_id": str(destination.id),
            "lines": [{"line_type": "SKU", "qty": 2, "snapshot": _line_snapshot(None, "PENDING")}],
        },
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]
    line_id = create.json()["lines"][0]["id"]

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "sku-dispatch-1"},
        json={"transaction_id": "txn-sku-dispatch-1", "action": "dispatch"},
    )
    assert dispatch.status_code == 200

    receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {destination_token}", "Idempotency-Key": "sku-receive-1"},
        json={"transaction_id": "txn-sku-receive-1", "action": "receive", "receive_lines": [{"line_id": line_id, "qty": 2}]},
    )
    assert receive.status_code == 200
    assert receive.json()["header"]["status"] == "RECEIVED"
    assert receive.json()["lines"][0]["received_qty"] == 2


def test_transfer_sku_dispatch_requires_available_pending_qty(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, origin_user, _destination_user = _create_context(db_session, suffix="sku-insufficient")
    origin_token = _login(client, origin_user.username, "Pass1234!")
    _seed_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc="2" * 24, sku_qty=1)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "sku-create-2"},
        json={
            "transaction_id": "txn-sku-create-2",
            "origin_store_id": str(origin.id),
            "destination_store_id": str(destination.id),
            "lines": [{"line_type": "SKU", "qty": 2, "snapshot": _line_snapshot(None, "PENDING")}],
        },
    )
    assert create.status_code == 409
    assert create.json()["code"] == "BUSINESS_CONFLICT"


def test_transfer_mixed_epc_and_sku_lines(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, origin_user, destination_user = _create_context(db_session, suffix="mixed")
    origin_token = _login(client, origin_user.username, "Pass1234!")
    destination_token = _login(client, destination_user.username, "Pass1234!")
    epc = "3" * 24
    _seed_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc=epc, sku_qty=2)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "mixed-create-1"},
        json={
            "transaction_id": "txn-mixed-create-1",
            "origin_store_id": str(origin.id),
            "destination_store_id": str(destination.id),
            "lines": [
                {"line_type": "EPC", "qty": 1, "snapshot": _line_snapshot(epc, "RFID")},
                {"line_type": "SKU", "qty": 2, "snapshot": _line_snapshot(None, "PENDING")},
            ],
        },
    )
    assert create.status_code == 201

    transfer_id = create.json()["header"]["id"]
    sku_line = next(line for line in create.json()["lines"] if line["line_type"] == "SKU")
    epc_line = next(line for line in create.json()["lines"] if line["line_type"] == "EPC")

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "mixed-dispatch-1"},
        json={"transaction_id": "txn-mixed-dispatch-1", "action": "dispatch"},
    )
    assert dispatch.status_code == 200

    receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {destination_token}", "Idempotency-Key": "mixed-receive-1"},
        json={
            "transaction_id": "txn-mixed-receive-1",
            "action": "receive",
            "receive_lines": [{"line_id": epc_line["id"], "qty": 1}, {"line_id": sku_line["id"], "qty": 2}],
        },
    )
    assert receive.status_code == 200
    assert receive.json()["header"]["status"] == "RECEIVED"
