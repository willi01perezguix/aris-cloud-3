import uuid
from datetime import datetime

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, TransferMovement, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_users(db_session, *, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    origin_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix} A")
    destination_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix} B")
    origin_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=origin_store.id,
        username=f"user-{suffix}-origin",
        email=f"user-{suffix}-origin@example.com",
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
        username=f"user-{suffix}-dest",
        email=f"user-{suffix}-dest@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    manager_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=destination_store.id,
        username=f"user-{suffix}-manager",
        email=f"user-{suffix}-manager@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="MANAGER",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    basic_user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=destination_store.id,
        username=f"user-{suffix}-basic",
        email=f"user-{suffix}-basic@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="USER",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([
        tenant,
        origin_store,
        destination_store,
        origin_user,
        destination_user,
        manager_user,
        basic_user,
    ])
    db_session.commit()
    return tenant, origin_store, destination_store, origin_user, destination_user, manager_user, basic_user


def _seed_stock(db_session, tenant_id, *, epc: str, qty: int):
    items = [
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
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
        )
    ]
    for _ in range(qty):
        items.append(
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                sku="SKU-2",
                description="Green Tee",
                var1_value="Green",
                var2_value="M",
                epc=None,
                location_code="LOC-1",
                pool="P1",
                status="PENDING",
                location_is_vendible=True,
                image_asset_id=uuid.uuid4(),
                image_url="https://example.com/img2.png",
                image_thumb_url="https://example.com/thumb2.png",
                image_source="catalog",
                image_updated_at=datetime.utcnow(),
            )
        )
    db_session.add_all(items)
    db_session.commit()


def _transfer_payload(origin_store_id: str, destination_store_id: str, epc: str, qty: int):
    return {
        "transaction_id": "txn-resolve-1",
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
            },
            {
                "line_type": "SKU",
                "qty": qty,
                "snapshot": {
                    "sku": "SKU-2",
                    "description": "Green Tee",
                    "var1_value": "Green",
                    "var2_value": "M",
                    "epc": None,
                    "location_code": "LOC-1",
                    "pool": "P1",
                    "status": "PENDING",
                    "location_is_vendible": True,
                    "image_asset_id": str(uuid.uuid4()),
                    "image_url": "https://example.com/img2.png",
                    "image_thumb_url": "https://example.com/thumb2.png",
                    "image_source": "catalog",
                    "image_updated_at": datetime.utcnow().isoformat(),
                },
            },
        ],
    }


def _setup_transfer(client, origin_token: str, dest_token: str, origin_store, destination_store, epc: str):
    payload = _transfer_payload(str(origin_store.id), str(destination_store.id), epc, qty=2)
    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "transfer-resolve-1"},
        json=payload,
    )
    assert create_response.status_code == 201
    transfer_id = create_response.json()["header"]["id"]
    lines = create_response.json()["lines"]

    dispatch_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "transfer-resolve-2"},
        json={"transaction_id": "txn-resolve-2", "action": "dispatch"},
    )
    assert dispatch_response.status_code == 200

    sku_line = next(line for line in lines if line["line_type"] == "SKU")

    receive_payload = {
        "transaction_id": "txn-resolve-3",
        "action": "receive",
        "receive_lines": [
            {
                "line_id": sku_line["id"],
                "qty": 1,
                "location_code": "DEST-1",
                "pool": "DP1",
                "location_is_vendible": True,
            }
        ],
    }
    receive_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-resolve-3"},
        json=receive_payload,
    )
    assert receive_response.status_code == 200

    shortage_payload = {
        "transaction_id": "txn-resolve-4",
        "action": "report_shortages",
        "shortages": [
            {
                "line_id": sku_line["id"],
                "qty": 1,
                "reason_code": "MISSING",
                "notes": "Not in box",
            }
        ],
    }
    shortage_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-resolve-4"},
        json=shortage_payload,
    )
    assert shortage_response.status_code == 200
    return transfer_id, lines, sku_line


def test_transfer_resolve_shortages_found_and_resend(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, origin_user, destination_user, _manager_user, _basic_user = (
        _create_tenant_users(db_session, suffix="resolve-found")
    )
    origin_token = _login(client, origin_user.username, "Pass1234!")
    dest_token = _login(client, destination_user.username, "Pass1234!")

    epc = "W" * 24
    _seed_stock(db_session, tenant.id, epc=epc, qty=2)

    transfer_id, _lines, sku_line = _setup_transfer(
        client, origin_token, dest_token, origin_store, destination_store, epc
    )

    resolve_payload = {
        "transaction_id": "txn-resolve-5",
        "action": "resolve_shortages",
        "resolution": {
            "resolution": "FOUND_AND_RESEND",
            "lines": [{"line_id": sku_line["id"], "qty": 1}],
        },
    }
    resolve_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-resolve-5"},
        json=resolve_payload,
    )
    assert resolve_response.status_code == 200
    sku_response = next(line for line in resolve_response.json()["lines"] if line["line_type"] == "SKU")
    assert sku_response["resolution_status"] == "FOUND_AND_RESEND"

    movement = (
        db_session.query(TransferMovement)
        .filter(
            TransferMovement.transfer_id == transfer_id,
            TransferMovement.action == "SHORTAGE_RESOLVED_FOUND_AND_RESEND",
        )
        .first()
    )
    assert movement is not None


def test_transfer_resolve_shortages_lost_in_route_manager(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, origin_user, _destination_user, manager_user, _basic_user = (
        _create_tenant_users(db_session, suffix="resolve-lost")
    )
    origin_token = _login(client, origin_user.username, "Pass1234!")
    manager_token = _login(client, manager_user.username, "Pass1234!")

    epc = "X" * 24
    _seed_stock(db_session, tenant.id, epc=epc, qty=2)

    transfer_id, lines, sku_line = _setup_transfer(
        client, origin_token, manager_token, origin_store, destination_store, epc
    )
    epc_line = next(line for line in lines if line["line_type"] == "EPC")
    receive_payload = {
        "transaction_id": "txn-resolve-6b",
        "action": "receive",
        "receive_lines": [
            {
                "line_id": epc_line["id"],
                "qty": 1,
                "location_code": "DEST-1",
                "pool": "DP1",
                "location_is_vendible": True,
            }
        ],
    }
    receive_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "transfer-resolve-6b"},
        json=receive_payload,
    )
    assert receive_response.status_code == 200

    resolve_payload = {
        "transaction_id": "txn-resolve-6",
        "action": "resolve_shortages",
        "resolution": {
            "resolution": "LOST_IN_ROUTE",
            "lines": [{"line_id": sku_line["id"], "qty": 1}],
        },
    }
    resolve_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "transfer-resolve-6"},
        json=resolve_payload,
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["header"]["status"] == "RECEIVED"

    in_transit = (
        db_session.query(StockItem)
        .filter(
            StockItem.tenant_id == tenant.id,
            StockItem.location_code == "IN_TRANSIT",
            StockItem.pool == "IN_TRANSIT",
        )
        .count()
    )
    assert in_transit == 0


def test_transfer_resolve_shortages_lost_in_route_denied_for_non_manager(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, origin_user, destination_user, _manager_user, basic_user = (
        _create_tenant_users(db_session, suffix="resolve-denied")
    )
    origin_token = _login(client, origin_user.username, "Pass1234!")
    dest_token = _login(client, destination_user.username, "Pass1234!")
    basic_token = _login(client, basic_user.username, "Pass1234!")

    epc = "Y" * 24
    _seed_stock(db_session, tenant.id, epc=epc, qty=2)

    transfer_id, _lines, sku_line = _setup_transfer(
        client, origin_token, dest_token, origin_store, destination_store, epc
    )

    resolve_payload = {
        "transaction_id": "txn-resolve-7",
        "action": "resolve_shortages",
        "resolution": {
            "resolution": "LOST_IN_ROUTE",
            "lines": [{"line_id": sku_line["id"], "qty": 1}],
        },
    }
    resolve_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {basic_token}", "Idempotency-Key": "transfer-resolve-7"},
        json=resolve_payload,
    )
    assert resolve_response.status_code == 403
    assert resolve_response.json()["code"] == ErrorCatalog.PERMISSION_DENIED.code


def test_transfer_resolve_shortages_invalid_payload_denied(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, origin_user, destination_user, _manager_user, _basic_user = (
        _create_tenant_users(db_session, suffix="resolve-invalid")
    )
    origin_token = _login(client, origin_user.username, "Pass1234!")
    dest_token = _login(client, destination_user.username, "Pass1234!")

    epc = "Z" * 24
    _seed_stock(db_session, tenant.id, epc=epc, qty=2)

    transfer_id, _lines, sku_line = _setup_transfer(
        client, origin_token, dest_token, origin_store, destination_store, epc
    )

    resolve_payload = {
        "transaction_id": "txn-resolve-8",
        "action": "resolve_shortages",
        "resolution": {
            "resolution": "FOUND_AND_RESEND",
            "lines": [{"line_id": sku_line["id"], "qty": 2}],
        },
    }
    resolve_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-resolve-8"},
        json=resolve_payload,
    )
    assert resolve_response.status_code == 422
    assert resolve_response.json()["code"] == ErrorCatalog.VALIDATION_ERROR.code
