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
