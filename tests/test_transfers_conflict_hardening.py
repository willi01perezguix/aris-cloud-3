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


def _bootstrap(db_session, suffix: str = "x"):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    bodega = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"BODEGA {suffix}")
    online = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"ONLINE {suffix}")
    user_bodega = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=bodega.id,
        username=f"bodega-{suffix}",
        email=f"bodega-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    user_online = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=online.id,
        username=f"online-{suffix}",
        email=f"online-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, bodega, online, user_bodega, user_online])
    db_session.commit()
    return tenant, bodega, online, user_bodega, user_online


def _seed_epc(db_session, *, tenant_id, store_id, epc: str):
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
            status="RFID",
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
        "transaction_id": f"txn-{uuid.uuid4()}",
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


def _create_transfer(client, token: str, payload: dict, key_suffix: str):
    return client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"k-{key_suffix}"},
        json=payload,
    )


def _dispatch_transfer(client, token: str, transfer_id: str, key_suffix: str):
    return client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"k-{key_suffix}"},
        json={"action": "dispatch", "transaction_id": f"txn-{key_suffix}"},
    )


def _receive_transfer(client, token: str, transfer_id: str, line_id: str, key_suffix: str):
    return client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"k-{key_suffix}"},
        json={
            "action": "receive",
            "transaction_id": f"txn-{key_suffix}",
            "receive_lines": [{"line_id": line_id, "qty": 1}],
        },
    )


def test_received_transfer_does_not_block_reverse_transfer(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, user_bodega, user_online = _bootstrap(db_session, "received-reverse")
    epc = "R" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=bodega.id, epc=epc)
    bodega_token = _login(client, user_bodega.username)
    online_token = _login(client, user_online.username)

    created = _create_transfer(client, bodega_token, _payload(str(bodega.id), str(online.id), epc), "received-reverse-1")
    assert created.status_code == 201
    transfer_id = created.json()["header"]["id"]
    line_id = created.json()["lines"][0]["id"]

    dispatched = _dispatch_transfer(client, bodega_token, transfer_id, "received-reverse-2")
    assert dispatched.status_code == 200

    received = _receive_transfer(client, online_token, transfer_id, line_id, "received-reverse-3")
    assert received.status_code == 200
    assert received.json()["header"]["status"] == "RECEIVED"

    reverse = _create_transfer(client, online_token, _payload(str(online.id), str(bodega.id), epc), "received-reverse-4")
    assert reverse.status_code == 201


def test_valid_active_draft_blocks_reverse_transfer(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, _, user_online = _bootstrap(db_session, "active-draft-block")
    epc = "S" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=online.id, epc=epc)
    online_token = _login(client, user_online.username)

    first = _create_transfer(client, online_token, _payload(str(online.id), str(bodega.id), epc), "active-draft-block-1")
    assert first.status_code == 201

    second = _create_transfer(client, online_token, _payload(str(online.id), str(bodega.id), epc), "active-draft-block-2")
    assert second.status_code == 409
    details = second.json().get("details", {})
    assert details.get("conflict_type") == "valid_active_transfer"
    assert details.get("blocking_status") == "DRAFT"


def test_stale_draft_conflict_is_explicit(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, user_bodega, _ = _bootstrap(db_session, "stale-draft")
    epc = "T" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=bodega.id, epc=epc)
    bodega_token = _login(client, user_bodega.username)

    created = _create_transfer(client, bodega_token, _payload(str(bodega.id), str(online.id), epc), "stale-draft-1")
    assert created.status_code == 201
    transfer_id = created.json()["header"]["id"]

    stock_row = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id, StockItem.epc == epc).one()
    stock_row.store_id = online.id
    db_session.commit()

    dispatch = _dispatch_transfer(client, bodega_token, transfer_id, "stale-draft-2")
    assert dispatch.status_code in {409, 422}
    assert dispatch.status_code != 500
    details = dispatch.json().get("details", {})
    assert details.get("conflict_type") == "stale_draft"
    assert details.get("blocking_transfer_id") == transfer_id
    assert details.get("actual_store_id") == str(online.id)


def test_conflict_response_includes_blocking_transfer_metadata(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, _, user_online = _bootstrap(db_session, "blocking-meta")
    epc = "U" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=online.id, epc=epc)
    online_token = _login(client, user_online.username)

    blocker = _create_transfer(client, online_token, _payload(str(online.id), str(bodega.id), epc), "blocking-meta-1")
    assert blocker.status_code == 201
    blocker_id = blocker.json()["header"]["id"]

    blocked = _create_transfer(client, online_token, _payload(str(online.id), str(bodega.id), epc), "blocking-meta-2")
    assert blocked.status_code == 409
    details = blocked.json().get("details", {})
    assert details.get("blocking_transfer_id") == blocker_id
    assert details.get("blocking_status") == "DRAFT"
    assert details.get("blocking_origin_store_id") == str(online.id)
    assert details.get("blocking_destination_store_id") == str(bodega.id)
    assert details.get("epc") == epc


def test_origin_store_mismatch_returns_actual_store(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, user_bodega, _ = _bootstrap(db_session, "origin-mismatch")
    epc = "V" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=online.id, epc=epc)
    bodega_token = _login(client, user_bodega.username)

    mismatch = _create_transfer(client, bodega_token, _payload(str(bodega.id), str(online.id), epc), "origin-mismatch-1")
    assert mismatch.status_code == 409
    details = mismatch.json().get("details", {})
    assert details.get("actual_store_id") == str(online.id)


def test_no_500_for_reverse_transfer_conflict_paths(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, user_bodega, user_online = _bootstrap(db_session, "no-500")
    epc = "W" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=online.id, epc=epc)
    bodega_token = _login(client, user_bodega.username)
    online_token = _login(client, user_online.username)

    active = _create_transfer(client, online_token, _payload(str(online.id), str(bodega.id), epc), "no-500-1")
    assert active.status_code == 201

    blocked = _create_transfer(client, online_token, _payload(str(online.id), str(bodega.id), epc), "no-500-2")
    assert blocked.status_code in {409, 422}
    assert blocked.status_code != 500

    wrong_origin = _create_transfer(client, bodega_token, _payload(str(bodega.id), str(online.id), epc), "no-500-3")
    assert wrong_origin.status_code in {409, 422}
    assert wrong_origin.status_code != 500
