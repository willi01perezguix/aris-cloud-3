import uuid
from datetime import datetime
from decimal import Decimal

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str = "Pass1234!") -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _bootstrap(db_session, suffix: str = "transfer-reg"):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    origin_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Origin {suffix}")
    destination_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Destination {suffix}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=origin_store.id,
        username=f"user-{suffix}",
        email=f"user-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, origin_store, destination_store, user])
    db_session.commit()
    return tenant, origin_store, destination_store, user


def _seed_epc(db_session, *, tenant_id, store_id, epc: str, status: str = "RFID"):
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            store_id=store_id,
            sku="SKU-1",
            description="Blue Jacket",
            var1_value="Blue",
            var2_value="L",
            epc=epc,
            location_code="LOC-1",
            pool="P1",
            status=status,
            location_is_vendible=True,
            image_asset_id=uuid.uuid4(),
            image_url="https://example.com/img.png",
            image_thumb_url="https://example.com/thumb.png",
            image_source="catalog",
            image_updated_at=datetime.utcnow(),
            cost_price=Decimal("25.00"),
            suggested_price=Decimal("35.00"),
            sale_price=Decimal("32.50"),
        )
    )
    db_session.commit()


def _payload(origin_store_id: str, destination_store_id: str, epc: str):
    return {
        "transaction_id": "txn-create-1",
        "origin_store_id": origin_store_id,
        "destination_store_id": destination_store_id,
        "lines": [
            {
                "line_type": "EPC",
                "qty": 1,
                "snapshot": {
                    "sku": "SKU-1",
                    "description": "Blue Jacket",
                    "var1_value": "Blue",
                    "var2_value": "L",
                    "epc": epc,
                    "location_code": "LOC-1",
                    "pool": "P1",
                    "status": "RFID",
                    "location_is_vendible": True,
                    "image_asset_id": str(uuid.uuid4()),
                    "image_url": "https://example.com/img.png",
                    "image_thumb_url": "https://example.com/thumb.png",
                    "image_source": "catalog",
                    "image_updated_at": datetime.utcnow().isoformat(),
                },
            }
        ],
    }


def test_create_transfer_epc_valid(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="create-valid")
    token = _login(client, user.username)
    epc = "A" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-create-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["header"]["status"] == "DRAFT"
    assert body["lines"][0]["qty"] == 1
    assert body["lines"][0]["received_qty"] == 0
    assert body["lines"][0]["outstanding_qty"] == 1
    assert body["movement_summary"]["dispatched_qty"] == 0


def test_create_transfer_rejects_epc_not_in_origin_store(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="create-not-origin")
    token = _login(client, user.username)
    epc = "B" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=destination_store.id, epc=epc)

    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-create-2"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )

    assert response.status_code in {409, 422}
    assert response.json()["code"] != "INTERNAL_ERROR"


def test_update_transfer_rejects_stale_epc(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="update-stale")
    token = _login(client, user.username)
    epc = "C" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-update-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]

    stock_row = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id, StockItem.epc == epc).one()
    stock_row.store_id = destination_store.id
    db_session.commit()

    update = client.patch(
        f"/aris3/transfers/{transfer_id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-update-2"},
        json={"transaction_id": "txn-update-1", "lines": _payload(str(origin_store.id), str(destination_store.id), epc)["lines"]},
    )
    assert update.status_code in {409, 422}
    assert update.json()["code"] != "INTERNAL_ERROR"


def test_update_transfer_rejects_stale_epc_without_line_changes(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="update-stale-no-lines")
    token = _login(client, user.username)
    epc = "L" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)
    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-update-stale-no-lines-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]
    stock_row = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id, StockItem.epc == epc).one()
    stock_row.store_id = destination_store.id
    db_session.commit()
    update = client.patch(
        f"/aris3/transfers/{transfer_id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-update-stale-no-lines-2"},
        json={"transaction_id": "txn-update-stale-no-lines-1", "destination_store_id": str(destination_store.id)},
    )
    assert update.status_code in {409, 422}
    assert update.json()["code"] != "INTERNAL_ERROR"


def test_dispatch_transfer_epc_from_draft(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="dispatch-draft")
    token = _login(client, user.username)
    epc = "D" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-dispatch-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-dispatch-2"},
        json={"action": "dispatch", "transaction_id": "txn-dispatch-1"},
    )
    assert dispatch.status_code == 200
    data = dispatch.json()
    assert data["header"]["status"] == "DISPATCHED"
    assert data["header"]["dispatched_at"] is not None
    assert data["header"]["dispatched_by_user_id"] is not None


def test_dispatch_never_throws_typeerror(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="dispatch-typeerror")
    token = _login(client, user.username)
    epc = "E" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-dispatch-3"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201

    transfer_id = create.json()["header"]["id"]
    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-dispatch-4"},
        json={"action": "dispatch", "transaction_id": "txn-dispatch-2"},
    )
    assert dispatch.status_code != 500
    assert dispatch.json().get("details", {}).get("type") != "TypeError"


def test_transfer_lines_consistency(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="lines-consistency")
    token = _login(client, user.username)
    epc = "F" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-consistency-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    draft = create.json()
    assert draft["lines"][0]["qty"] == 1
    assert draft["lines"][0]["received_qty"] == 0
    assert draft["lines"][0]["outstanding_qty"] == 1

    transfer_id = draft["header"]["id"]
    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-consistency-2"},
        json={"action": "dispatch", "transaction_id": "txn-dispatch-3"},
    )
    assert dispatch.status_code == 200
    moved = dispatch.json()
    assert moved["movement_summary"]["dispatched_lines"] == 1
    assert moved["movement_summary"]["dispatched_qty"] == 1
    assert moved["lines"][0]["outstanding_qty"] == 1


def test_reject_non_epc_transfer_lines(client, db_session):
    run_seed(db_session)
    _, origin_store, destination_store, user = _bootstrap(db_session, suffix="reject-sku")
    token = _login(client, user.username)

    payload = _payload(str(origin_store.id), str(destination_store.id), "G" * 24)
    payload["lines"][0]["line_type"] = "SKU"
    payload["lines"][0]["snapshot"]["epc"] = None

    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-non-epc-1"},
        json=payload,
    )

    assert response.status_code in {409, 422}
    assert response.json()["code"] != "INTERNAL_ERROR"


def test_receive_transfer_epc(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="receive-epc")
    destination_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=destination_store.id,
        username="user-receive-epc-dest",
        email="user-receive-epc-dest@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add(destination_user)
    db_session.commit()
    token = _login(client, user.username)
    destination_token = _login(client, destination_user.username)
    epc = "H" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-receive-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]
    line_id = create.json()["lines"][0]["id"]

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-receive-2"},
        json={"action": "dispatch", "transaction_id": "txn-receive-dispatch-1"},
    )
    assert dispatch.status_code == 200

    receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {destination_token}", "Idempotency-Key": "reg-receive-3"},
        json={
            "action": "receive",
            "transaction_id": "txn-receive-1",
            "receive_lines": [{"line_id": line_id, "qty": 1, "location_code": "STORE-DEST", "pool": "SALE"}],
        },
    )
    assert receive.status_code == 200
    body = receive.json()
    assert body["header"]["status"] == "RECEIVED"
    assert body["lines"][0]["received_qty"] == 1
    assert body["lines"][0]["outstanding_qty"] == 0


def test_cancel_transfer_valid(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="cancel-valid")
    token = _login(client, user.username)
    epc = "I" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-cancel-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]
    cancel = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-cancel-2"},
        json={"action": "cancel", "transaction_id": "txn-cancel-1"},
    )
    assert cancel.status_code == 200
    assert cancel.json()["header"]["status"] == "CANCELED"


def test_non_epc_transfer_lines_rejected(client, db_session):
    run_seed(db_session)
    _, origin_store, destination_store, user = _bootstrap(db_session, suffix="reject-non-epc")
    token = _login(client, user.username)
    payload = _payload(str(origin_store.id), str(destination_store.id), "J" * 24)
    payload["lines"][0]["line_type"] = "SKU"
    payload["lines"][0]["snapshot"]["epc"] = None
    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-non-epc-2"},
        json=payload,
    )
    assert response.status_code in {409, 422}
    assert response.json()["code"] != "INTERNAL_ERROR"


def test_movement_summary_consistency(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="movement-summary")
    destination_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=destination_store.id,
        username="user-movement-summary-dest",
        email="user-movement-summary-dest@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add(destination_user)
    db_session.commit()
    token = _login(client, user.username)
    destination_token = _login(client, destination_user.username)
    epc = "K" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)
    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-summary-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    created = create.json()
    assert created["movement_summary"]["dispatched_lines"] == 0
    assert created["movement_summary"]["dispatched_qty"] == 0
    assert created["movement_summary"]["pending_reception"] is False
    transfer_id = created["header"]["id"]
    line_id = created["lines"][0]["id"]

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-summary-2"},
        json={"action": "dispatch", "transaction_id": "txn-summary-dispatch-1"},
    )
    assert dispatch.status_code == 200
    dispatched = dispatch.json()
    assert dispatched["movement_summary"]["dispatched_lines"] == 1
    assert dispatched["movement_summary"]["dispatched_qty"] == 1
    assert dispatched["movement_summary"]["pending_reception"] is True

    receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {destination_token}", "Idempotency-Key": "reg-summary-3"},
        json={
            "action": "receive",
            "transaction_id": "txn-summary-receive-1",
            "receive_lines": [{"line_id": line_id, "qty": 1}],
        },
    )
    assert receive.status_code == 200
    received = receive.json()
    assert received["movement_summary"]["dispatched_lines"] == 1
    assert received["movement_summary"]["dispatched_qty"] == 1
    assert received["movement_summary"]["pending_reception"] is False
    assert received["movement_summary"]["shortages_possible"] is False


def test_create_transfer_rejects_epc_already_in_active_transfer(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="create-active-conflict")
    token = _login(client, user.username)
    epc = "M" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    first = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-active-conflict-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert first.status_code == 201

    second = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-active-conflict-2"},
        json={**_payload(str(origin_store.id), str(destination_store.id), epc), "transaction_id": "txn-active-conflict-2"},
    )
    assert second.status_code in {409, 422}
    assert second.json()["code"] in {"BUSINESS_CONFLICT", "VALIDATION_ERROR"}


def test_dispatch_transfer_revalidates_stock(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="dispatch-revalidate")
    token = _login(client, user.username)
    epc = "N" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-dispatch-revalidate-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]

    stock_row = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id, StockItem.epc == epc).one()
    stock_row.store_id = destination_store.id
    db_session.commit()

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-dispatch-revalidate-2"},
        json={"action": "dispatch", "transaction_id": "txn-dispatch-revalidate-1"},
    )
    assert dispatch.status_code in {409, 422}
    assert dispatch.status_code != 500
    assert dispatch.json()["code"] in {"BUSINESS_CONFLICT", "VALIDATION_ERROR"}


def test_dispatch_transfer_blocks_reuse_of_epc(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="dispatch-reuse-block")
    token = _login(client, user.username)
    epc = "O" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-reuse-block-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]
    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-reuse-block-2"},
        json={"action": "dispatch", "transaction_id": "txn-reuse-block-dispatch-1"},
    )
    assert dispatch.status_code == 200

    second = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-reuse-block-3"},
        json={**_payload(str(origin_store.id), str(destination_store.id), epc), "transaction_id": "txn-reuse-block-create-2"},
    )
    assert second.status_code in {409, 422}
    assert second.status_code != 500


def test_received_epc_not_available_in_origin_after_receive(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="received-not-origin")
    destination_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=destination_store.id,
        username="user-received-not-origin-dest",
        email="user-received-not-origin-dest@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add(destination_user)
    db_session.commit()
    token = _login(client, user.username)
    destination_token = _login(client, destination_user.username)
    epc = "P" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-received-not-origin-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]
    line_id = create.json()["lines"][0]["id"]
    assert (
        client.post(
            f"/aris3/transfers/{transfer_id}/actions",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-received-not-origin-2"},
            json={"action": "dispatch", "transaction_id": "txn-received-not-origin-dispatch"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/aris3/transfers/{transfer_id}/actions",
            headers={"Authorization": f"Bearer {destination_token}", "Idempotency-Key": "reg-received-not-origin-3"},
            json={"action": "receive", "transaction_id": "txn-received-not-origin-receive", "receive_lines": [{"line_id": line_id, "qty": 1}]},
        ).status_code
        == 200
    )

    second = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-received-not-origin-4"},
        json={**_payload(str(origin_store.id), str(destination_store.id), epc), "transaction_id": "txn-received-not-origin-create-2"},
    )
    assert second.status_code in {409, 422}
    assert second.status_code != 500


def test_cancel_draft_restores_origin_availability(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="cancel-draft-availability")
    token = _login(client, user.username)
    epc = "Q" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-cancel-draft-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]
    cancel = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-cancel-draft-2"},
        json={"action": "cancel", "transaction_id": "txn-cancel-draft-1"},
    )
    assert cancel.status_code == 200

    create_again = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-cancel-draft-3"},
        json={**_payload(str(origin_store.id), str(destination_store.id), epc), "transaction_id": "txn-cancel-draft-2"},
    )
    assert create_again.status_code == 201


def test_transfer_never_returns_500_for_business_validation(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, user = _bootstrap(db_session, suffix="never-500-business")
    token = _login(client, user.username)
    epc = "R" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=origin_store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-never500-1"},
        json=_payload(str(origin_store.id), str(destination_store.id), epc),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]

    stock_row = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id, StockItem.epc == epc).one()
    stock_row.store_id = destination_store.id
    db_session.commit()

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "reg-never500-2"},
        json={"action": "dispatch", "transaction_id": "txn-never500-dispatch-1"},
    )
    assert dispatch.status_code in {409, 422}
    assert dispatch.status_code != 500
    assert dispatch.json()["code"] != "INTERNAL_ERROR"
