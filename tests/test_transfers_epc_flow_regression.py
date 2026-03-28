import uuid
from datetime import datetime

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
    external_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"External {suffix}")
    origin_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=origin_store.id,
        username=f"origin-{suffix}",
        email=f"origin-{suffix}@example.com",
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
        username=f"destination-{suffix}",
        email=f"destination-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, origin_store, destination_store, external_store, origin_user, destination_user])
    db_session.commit()
    return tenant, origin_store, destination_store, external_store, origin_user, destination_user


def _seed_epc_stock(db_session, *, tenant_id, store_id, epc: str):
    item = StockItem(
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
        image_asset_id=uuid.uuid4(),
        image_url="https://example.com/image.png",
        image_thumb_url="https://example.com/thumb.png",
        image_source="catalog",
        image_updated_at=datetime.utcnow(),
    )
    db_session.add(item)
    db_session.commit()


def _transfer_payload(origin_store_id: str, destination_store_id: str, epc: str):
    return {
        "transaction_id": f"txn-create-{epc}",
        "origin_store_id": origin_store_id,
        "destination_store_id": destination_store_id,
        "lines": [
            {
                "line_type": "EPC",
                "qty": 1,
                "snapshot": {
                    "sku": "SKU-1",
                    "description": "transfer",
                    "var1_value": "Blue",
                    "var2_value": "L",
                    "epc": epc,
                    "location_code": "LOC-1",
                    "pool": "P1",
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
    }


def test_create_transfer_epc_valid(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, _external, origin_user, _dest_user = _create_context(db_session, suffix="epc-valid")
    token = _login(client, origin_user.username, "Pass1234!")
    epc = "1" * 24
    _seed_epc_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc=epc)

    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "epc-valid-create"},
        json=_transfer_payload(str(origin.id), str(destination.id), epc),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["header"]["status"] == "DRAFT"
    assert body["lines"][0]["qty"] == 1
    assert body["lines"][0]["received_qty"] == 0
    assert body["lines"][0]["outstanding_qty"] == 1


def test_create_transfer_rejects_epc_not_in_origin_store(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, external, origin_user, _dest_user = _create_context(db_session, suffix="create-reject")
    token = _login(client, origin_user.username, "Pass1234!")
    epc = "2" * 24
    _seed_epc_stock(db_session, tenant_id=tenant.id, store_id=external.id, epc=epc)

    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "epc-not-origin"},
        json=_transfer_payload(str(origin.id), str(destination.id), epc),
    )

    assert response.status_code in {409, 422}
    assert response.status_code != 500


def test_update_transfer_rejects_stale_epc(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, external, origin_user, _dest_user = _create_context(db_session, suffix="update-stale")
    token = _login(client, origin_user.username, "Pass1234!")
    epc = "3" * 24
    _seed_epc_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "update-stale-create"},
        json=_transfer_payload(str(origin.id), str(destination.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]

    stock = db_session.query(StockItem).filter(StockItem.epc == epc).first()
    stock.store_id = external.id
    stock.updated_at = datetime.utcnow()
    db_session.commit()

    update = client.patch(
        f"/aris3/transfers/{transfer_id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "update-stale-patch"},
        json={"transaction_id": "txn-update-stale"},
    )

    assert update.status_code in {409, 422}
    assert update.status_code != 500


def test_dispatch_transfer_epc_from_draft(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, _external, origin_user, _dest_user = _create_context(db_session, suffix="dispatch-ok")
    token = _login(client, origin_user.username, "Pass1234!")
    epc = "4" * 24
    _seed_epc_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "dispatch-create"},
        json=_transfer_payload(str(origin.id), str(destination.id), epc),
    )
    transfer_id = create.json()["header"]["id"]

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "dispatch-action"},
        json={"transaction_id": "txn-dispatch-min", "action": "dispatch"},
    )

    assert dispatch.status_code == 200
    payload = dispatch.json()
    assert payload["header"]["status"] == "DISPATCHED"
    assert payload["header"]["dispatched_at"] is not None
    assert payload["header"]["dispatched_by_user_id"] is not None


def test_dispatch_never_throws_typeerror(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, _external, origin_user, _dest_user = _create_context(db_session, suffix="dispatch-type")
    token = _login(client, origin_user.username, "Pass1234!")
    epc = "5" * 24
    _seed_epc_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "dispatch-type-create"},
        json=_transfer_payload(str(origin.id), str(destination.id), epc),
    )
    transfer_id = create.json()["header"]["id"]

    response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "dispatch-type-action"},
        json={"transaction_id": "txn-dispatch-type", "action": "dispatch"},
    )

    assert response.status_code != 500
    body = response.json()
    assert body.get("code") != "INTERNAL_ERROR"


def test_receive_transfer_epc(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, _external, origin_user, destination_user = _create_context(db_session, suffix="receive-ok")
    origin_token = _login(client, origin_user.username, "Pass1234!")
    destination_token = _login(client, destination_user.username, "Pass1234!")
    epc = "6" * 24
    _seed_epc_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "receive-create"},
        json=_transfer_payload(str(origin.id), str(destination.id), epc),
    )
    transfer_id = create.json()["header"]["id"]
    line_id = create.json()["lines"][0]["id"]

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "receive-dispatch"},
        json={"transaction_id": "txn-receive-dispatch", "action": "dispatch"},
    )
    assert dispatch.status_code == 200

    receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {destination_token}", "Idempotency-Key": "receive-action"},
        json={"transaction_id": "txn-receive", "action": "receive", "receive_lines": [{"line_id": line_id, "qty": 1}]},
    )

    assert receive.status_code == 200
    body = receive.json()
    assert body["header"]["status"] == "RECEIVED"
    assert body["lines"][0]["received_qty"] == 1
    assert body["lines"][0]["outstanding_qty"] == 0


def test_cancel_transfer_valid(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, _external, origin_user, _dest_user = _create_context(db_session, suffix="cancel-ok")
    token = _login(client, origin_user.username, "Pass1234!")
    epc = "7" * 24
    _seed_epc_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cancel-create"},
        json=_transfer_payload(str(origin.id), str(destination.id), epc),
    )
    transfer_id = create.json()["header"]["id"]

    cancel = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "cancel-action"},
        json={"transaction_id": "txn-cancel", "action": "cancel"},
    )

    assert cancel.status_code == 200
    assert cancel.json()["header"]["status"] == "CANCELED"


def test_non_epc_transfer_lines_rejected(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, _external, origin_user, _dest_user = _create_context(db_session, suffix="non-epc")
    token = _login(client, origin_user.username, "Pass1234!")
    epc = "8" * 24
    _seed_epc_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc=epc)

    sku_payload = _transfer_payload(str(origin.id), str(destination.id), epc)
    sku_payload["lines"][0]["line_type"] = "SKU"
    sku_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "sku-line"},
        json=sku_payload,
    )
    assert sku_response.status_code in {409, 422}
    assert sku_response.status_code != 500

    missing_epc_payload = _transfer_payload(str(origin.id), str(destination.id), epc)
    missing_epc_payload["lines"][0]["snapshot"]["epc"] = None
    missing_epc_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "missing-epc"},
        json=missing_epc_payload,
    )
    assert missing_epc_response.status_code in {409, 422}
    assert missing_epc_response.status_code != 500


def test_movement_summary_consistency(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, _external, origin_user, destination_user = _create_context(db_session, suffix="summary")
    origin_token = _login(client, origin_user.username, "Pass1234!")
    destination_token = _login(client, destination_user.username, "Pass1234!")
    epc = "9" * 24
    _seed_epc_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "summary-create"},
        json=_transfer_payload(str(origin.id), str(destination.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]
    line_id = create.json()["lines"][0]["id"]
    assert create.json()["movement_summary"]["dispatched_qty"] == 0
    assert create.json()["movement_summary"]["pending_reception"] is False

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "summary-dispatch"},
        json={"transaction_id": "txn-summary-dispatch", "action": "dispatch"},
    )
    assert dispatch.status_code == 200
    assert dispatch.json()["movement_summary"]["dispatched_qty"] == 1
    assert dispatch.json()["movement_summary"]["pending_reception"] is True

    receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {destination_token}", "Idempotency-Key": "summary-receive"},
        json={"transaction_id": "txn-summary-receive", "action": "receive", "receive_lines": [{"line_id": line_id, "qty": 1}]},
    )
    assert receive.status_code == 200
    assert receive.json()["movement_summary"]["pending_reception"] is False
