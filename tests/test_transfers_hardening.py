import uuid
from datetime import datetime

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
    other_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix} B")
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
    db_session.add_all([tenant, store, other_store, user])
    db_session.commit()
    return tenant, store, other_store, user


def _seed_epc_stock(db_session, tenant_id, store_id, *, epc: str, status: str = "RFID"):
    item = StockItem(
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
    )
    db_session.add(item)
    db_session.commit()


def _transfer_payload(origin_store_id: str, destination_store_id: str, epc: str):
    return {
        "transaction_id": "txn-harden-1",
        "origin_store_id": origin_store_id,
        "destination_store_id": destination_store_id,
        "lines": [
            {
                "line_type": "EPC",
                "qty": 1,
                "snapshot": {
                    "sku": "SKU-1",
                    "description": "spoof",
                    "var1_value": "spoof",
                    "var2_value": "spoof",
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


def test_transfer_enforces_origin_scope_and_snapshot_normalization(client, db_session):
    run_seed(db_session)
    tenant, store, other_store, user = _create_tenant_user(db_session, suffix="h-1")
    token = _login(client, user.username, "Pass1234!")
    epc = "F" * 24
    _seed_epc_stock(db_session, tenant.id, store.id, epc=epc)

    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tr-hard-2"},
        json=_transfer_payload(str(store.id), str(other_store.id), epc),
    )
    assert response.status_code == 201
    line_snapshot = response.json()["lines"][0]["snapshot"]
    assert line_snapshot["description"] == "Blue Jacket"
    assert line_snapshot["image_url"] == "https://example.com/img.png"


def test_transfer_rejects_pending_and_epc_missing(client, db_session):
    run_seed(db_session)
    tenant, store, other_store, user = _create_tenant_user(db_session, suffix="h-2")
    token = _login(client, user.username, "Pass1234!")
    epc = "A" * 24
    _seed_epc_stock(db_session, tenant.id, store.id, epc=epc, status="PENDING")

    payload = _transfer_payload(str(store.id), str(other_store.id), epc)
    resp = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tr-hard-3"},
        json=payload,
    )
    assert resp.status_code == 422

    payload["lines"][0]["snapshot"]["epc"] = None
    resp = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tr-hard-4"},
        json=payload,
    )
    assert resp.status_code == 422


def test_transfer_state_and_receive_guards(client, db_session):
    run_seed(db_session)
    tenant, store, other_store, user = _create_tenant_user(db_session, suffix="h-3")
    _tenant2, store2, other2, user2 = _create_tenant_user(db_session, suffix="h-4")
    token = _login(client, user.username, "Pass1234!")
    token2 = _login(client, user2.username, "Pass1234!")
    epc = "B" * 24
    _seed_epc_stock(db_session, tenant.id, store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tr-hard-5"},
        json=_transfer_payload(str(store.id), str(other_store.id), epc),
    )
    transfer_id = create.json()["header"]["id"]
    line_id = create.json()["lines"][0]["id"]

    before_dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tr-hard-6"},
        json={"transaction_id": "x", "action": "receive", "receive_lines": [{"line_id": line_id, "qty": 1}]},
    )
    assert before_dispatch.status_code == 422

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tr-hard-7"},
        json={"transaction_id": "x2", "action": "dispatch"},
    )
    assert dispatch.status_code == 200

    second_dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tr-hard-8"},
        json={"transaction_id": "x3", "action": "dispatch"},
    )
    assert second_dispatch.status_code == 422

    patch_after = client.patch(
        f"/aris3/transfers/{transfer_id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tr-hard-9"},
        json={"transaction_id": "x4", "lines": [_transfer_payload(str(store.id), str(other_store.id), epc)["lines"][0]]},
    )
    assert patch_after.status_code == 422

    wrong_receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token2}", "Idempotency-Key": "tr-hard-10"},
        json={"transaction_id": "x5", "action": "receive", "receive_lines": [{"line_id": line_id, "qty": 1}]},
    )
    assert wrong_receive.status_code == 422


def test_transfers_filters_scope_and_stores_endpoint(client, db_session):
    run_seed(db_session)
    tenant, store, other_store, user = _create_tenant_user(db_session, suffix="h-5")
    token = _login(client, user.username, "Pass1234!")
    epc = "C" * 24
    _seed_epc_stock(db_session, tenant.id, store.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "tr-hard-11"},
        json=_transfer_payload(str(store.id), str(other_store.id), epc),
    )
    assert create.status_code == 201

    rows = client.get(
        f"/aris3/transfers?status=DRAFT&origin_store_id={store.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rows.status_code == 200
    assert rows.json()["rows"]

    stores = client.get("/aris3/stores", headers={"Authorization": f"Bearer {token}"})
    assert stores.status_code == 200
    assert len(stores.json()["rows"]) == 2

    detail = client.get(
        f"/aris3/transfers/{create.json()['header']['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["lines"][0]["snapshot"]["image_thumb_url"] == "https://example.com/thumb.png"
