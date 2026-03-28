import uuid
from datetime import datetime
from decimal import Decimal

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, Transfer, TransferLine, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str = "Pass1234!") -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _bootstrap(db_session, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    bodega = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Bodega {suffix}")
    online = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Online {suffix}")

    bodega_user = User(
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
    online_user = User(
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

    db_session.add_all([tenant, bodega, online, bodega_user, online_user])
    db_session.commit()
    return tenant, bodega, online, bodega_user, online_user


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


def _payload(origin_store_id: str, destination_store_id: str, epc: str, transaction_id: str):
    return {
        "transaction_id": transaction_id,
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


def _create_dispatch_receive(client, bodega_token: str, online_token: str, bodega_id: str, online_id: str, epc: str, key_prefix: str):
    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {bodega_token}", "Idempotency-Key": f"{key_prefix}-create"},
        json=_payload(bodega_id, online_id, epc, f"{key_prefix}-txn-create"),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]

    dispatch = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {bodega_token}", "Idempotency-Key": f"{key_prefix}-dispatch"},
        json={"action": "dispatch", "transaction_id": f"{key_prefix}-txn-dispatch"},
    )
    assert dispatch.status_code == 200

    line_id = dispatch.json()["lines"][0]["id"]
    receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {online_token}", "Idempotency-Key": f"{key_prefix}-receive"},
        json={
            "action": "receive",
            "transaction_id": f"{key_prefix}-txn-receive",
            "receive_lines": [
                {
                    "line_id": line_id,
                    "qty": 1,
                    "location_code": "ONLINE-1",
                    "pool": "VENTA",
                    "location_is_vendible": True,
                }
            ],
        },
    )
    assert receive.status_code == 200
    return transfer_id, line_id


def test_reverse_transfer_allowed_after_full_receive(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, bodega_user, online_user = _bootstrap(db_session, "reverse-allowed")
    bodega_token = _login(client, bodega_user.username)
    online_token = _login(client, online_user.username)
    epc = "R" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=bodega.id, epc=epc)

    _create_dispatch_receive(
        client,
        bodega_token,
        online_token,
        str(bodega.id),
        str(online.id),
        epc,
        "reverse-allowed",
    )

    reverse = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {online_token}", "Idempotency-Key": "reverse-allowed-create-2"},
        json=_payload(str(online.id), str(bodega.id), epc, "reverse-allowed-txn-2"),
    )

    assert reverse.status_code == 201, reverse.json()


def test_transfer_blocked_while_previous_transfer_is_still_active(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, bodega_user, _online_user = _bootstrap(db_session, "active-block")
    bodega_token = _login(client, bodega_user.username)
    epc = "S" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=bodega.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {bodega_token}", "Idempotency-Key": "active-block-create-1"},
        json=_payload(str(bodega.id), str(online.id), epc, "active-block-txn-1"),
    )
    assert create.status_code == 201

    duplicate = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {bodega_token}", "Idempotency-Key": "active-block-create-2"},
        json=_payload(str(bodega.id), str(online.id), epc, "active-block-txn-2"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "BUSINESS_CONFLICT"


def test_received_transfer_no_longer_counts_as_active_commitment(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, bodega_user, online_user = _bootstrap(db_session, "received-not-active")
    bodega_token = _login(client, bodega_user.username)
    online_token = _login(client, online_user.username)
    epc = "T" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=bodega.id, epc=epc)

    transfer_id, _line_id = _create_dispatch_receive(
        client,
        bodega_token,
        online_token,
        str(bodega.id),
        str(online.id),
        epc,
        "received-not-active",
    )

    transfer = db_session.query(Transfer).filter(Transfer.id == transfer_id).one()
    assert transfer.status == "RECEIVED"

    active_commitment = (
        db_session.query(TransferLine)
        .join(Transfer, Transfer.id == TransferLine.transfer_id)
        .filter(
            Transfer.tenant_id == tenant.id,
            TransferLine.epc == epc,
            Transfer.status.in_({"DRAFT", "DISPATCHED", "PARTIAL_RECEIVED"}),
        )
        .first()
    )
    assert active_commitment is None


def test_stock_owner_store_matches_received_destination(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, bodega_user, online_user = _bootstrap(db_session, "received-owner")
    bodega_token = _login(client, bodega_user.username)
    online_token = _login(client, online_user.username)
    epc = "U" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=bodega.id, epc=epc)

    _create_dispatch_receive(
        client,
        bodega_token,
        online_token,
        str(bodega.id),
        str(online.id),
        epc,
        "received-owner",
    )

    stock = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id, StockItem.epc == epc).one()
    assert str(stock.store_id) == str(online.id)
    assert stock.location_code == "ONLINE-1"
    assert stock.pool == "VENTA"
    assert stock.location_is_vendible is True


def test_cancel_releases_epc_when_business_rules_allow_it(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, bodega_user, _online_user = _bootstrap(db_session, "cancel-release")
    bodega_token = _login(client, bodega_user.username)
    epc = "V" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=bodega.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {bodega_token}", "Idempotency-Key": "cancel-release-create"},
        json=_payload(str(bodega.id), str(online.id), epc, "cancel-release-txn-1"),
    )
    assert create.status_code == 201
    transfer_id = create.json()["header"]["id"]

    cancel = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {bodega_token}", "Idempotency-Key": "cancel-release-cancel"},
        json={"action": "cancel", "transaction_id": "cancel-release-txn-cancel"},
    )
    assert cancel.status_code == 200
    assert cancel.json()["header"]["status"] == "CANCELED"

    recreate = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {bodega_token}", "Idempotency-Key": "cancel-release-recreate"},
        json=_payload(str(bodega.id), str(online.id), epc, "cancel-release-txn-2"),
    )
    assert recreate.status_code == 201


def test_no_500_for_transfer_conflict_paths(client, db_session):
    run_seed(db_session)
    tenant, bodega, online, bodega_user, online_user = _bootstrap(db_session, "no-500-conflict")
    bodega_token = _login(client, bodega_user.username)
    online_token = _login(client, online_user.username)
    epc = "W" * 24
    _seed_epc(db_session, tenant_id=tenant.id, store_id=bodega.id, epc=epc)

    create = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {bodega_token}", "Idempotency-Key": "no-500-create-1"},
        json=_payload(str(bodega.id), str(online.id), epc, "no-500-txn-1"),
    )
    assert create.status_code == 201

    duplicate = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {bodega_token}", "Idempotency-Key": "no-500-create-2"},
        json=_payload(str(bodega.id), str(online.id), epc, "no-500-txn-2"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "BUSINESS_CONFLICT"

    wrong_origin_after_receive = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {online_token}", "Idempotency-Key": "no-500-create-3"},
        json=_payload(str(online.id), str(bodega.id), "Z" * 24, "no-500-txn-3"),
    )
    assert wrong_origin_after_receive.status_code in {409, 422}
    assert wrong_origin_after_receive.status_code != 500
