import uuid
from datetime import datetime

from app.aris3.core.error_catalog import ErrorCatalog
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import AuditEvent, StockItem, Store, Tenant, User
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
    db_session.add_all([tenant, origin_store, destination_store, origin_user, destination_user])
    db_session.commit()
    return tenant, origin_store, destination_store, origin_user, destination_user


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
        "transaction_id": "txn-idem-1",
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


def _prepare_transfer(client, origin_token: str, dest_token: str, origin_store, destination_store, epc: str):
    payload = _transfer_payload(str(origin_store.id), str(destination_store.id), epc, qty=2)
    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "transfer-idem-1"},
        json=payload,
    )
    assert create_response.status_code == 201
    transfer_id = create_response.json()["header"]["id"]
    lines = create_response.json()["lines"]

    dispatch_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "transfer-idem-2"},
        json={"transaction_id": "txn-idem-2", "action": "dispatch"},
    )
    assert dispatch_response.status_code == 200

    sku_line = next(line for line in lines if line["line_type"] == "SKU")
    receive_payload = {
        "transaction_id": "txn-idem-3",
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
        headers={"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-idem-3"},
        json=receive_payload,
    )
    assert receive_response.status_code == 200

    return transfer_id, lines, sku_line


def test_transfer_actions_idempotency_replay_and_conflict(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, origin_user, destination_user = _create_tenant_users(
        db_session, suffix="idem"
    )
    origin_token = _login(client, origin_user.username, "Pass1234!")
    dest_token = _login(client, destination_user.username, "Pass1234!")

    epc = "I" * 24
    _seed_stock(db_session, tenant.id, epc=epc, qty=2)

    transfer_id, lines, sku_line = _prepare_transfer(
        client, origin_token, dest_token, origin_store, destination_store, epc
    )

    receive_payload = {
        "transaction_id": "txn-idem-4",
        "action": "receive",
        "receive_lines": [
            {
                "line_id": lines[0]["id"],
                "qty": 1,
                "location_code": "DEST-2",
                "pool": "DP2",
                "location_is_vendible": True,
            }
        ],
    }
    headers = {"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-idem-4"}
    first_receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers=headers,
        json=receive_payload,
    )
    assert first_receive.status_code == 200

    replay_receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers=headers,
        json=receive_payload,
    )
    assert replay_receive.status_code == 200
    assert replay_receive.json() == first_receive.json()
    assert replay_receive.headers.get("X-Idempotency-Result") == ErrorCatalog.IDEMPOTENCY_REPLAY.code

    conflict_receive = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers=headers,
        json={
            **receive_payload,
            "transaction_id": "txn-idem-5",
        },
    )
    assert conflict_receive.status_code == 409
    assert conflict_receive.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code

    shortage_payload = {
        "transaction_id": "txn-idem-6",
        "action": "report_shortages",
        "shortages": [
            {
                "line_id": sku_line["id"],
                "qty": 1,
                "reason_code": "MISSING",
                "notes": "Not in tote",
            }
        ],
    }
    shortage_headers = {"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-idem-6"}
    first_shortage = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers=shortage_headers,
        json=shortage_payload,
    )
    assert first_shortage.status_code == 200

    replay_shortage = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers=shortage_headers,
        json=shortage_payload,
    )
    assert replay_shortage.status_code == 200
    assert replay_shortage.json() == first_shortage.json()

    conflict_shortage = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers=shortage_headers,
        json={
            **shortage_payload,
            "transaction_id": "txn-idem-7",
        },
    )
    assert conflict_shortage.status_code == 409
    assert conflict_shortage.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code

    resolve_payload = {
        "transaction_id": "txn-idem-8",
        "action": "resolve_shortages",
        "resolution": {
            "resolution": "FOUND_AND_RESEND",
            "lines": [{"line_id": sku_line["id"], "qty": 1}],
        },
    }
    resolve_headers = {"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-idem-8"}
    first_resolve = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers=resolve_headers,
        json=resolve_payload,
    )
    assert first_resolve.status_code == 200

    replay_resolve = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers=resolve_headers,
        json=resolve_payload,
    )
    assert replay_resolve.status_code == 200
    assert replay_resolve.json() == first_resolve.json()

    conflict_resolve = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers=resolve_headers,
        json={
            **resolve_payload,
            "transaction_id": "txn-idem-9",
        },
    )
    assert conflict_resolve.status_code == 409
    assert conflict_resolve.json()["code"] == ErrorCatalog.IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD.code


def test_transfer_actions_audit_events(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, origin_user, destination_user = _create_tenant_users(
        db_session, suffix="audit"
    )
    origin_token = _login(client, origin_user.username, "Pass1234!")
    dest_token = _login(client, destination_user.username, "Pass1234!")

    epc = "J" * 24
    _seed_stock(db_session, tenant.id, epc=epc, qty=2)

    transfer_id, _lines, sku_line = _prepare_transfer(
        client, origin_token, dest_token, origin_store, destination_store, epc
    )

    shortage_payload = {
        "transaction_id": "txn-audit-1",
        "action": "report_shortages",
        "shortages": [
            {
                "line_id": sku_line["id"],
                "qty": 1,
                "reason_code": "MISSING",
                "notes": "Not in tote",
            }
        ],
    }
    report_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-audit-1"},
        json=shortage_payload,
    )
    assert report_response.status_code == 200

    resolve_payload = {
        "transaction_id": "txn-audit-2",
        "action": "resolve_shortages",
        "resolution": {
            "resolution": "FOUND_AND_RESEND",
            "lines": [{"line_id": sku_line["id"], "qty": 1}],
        },
    }
    resolve_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-audit-2"},
        json=resolve_payload,
    )
    assert resolve_response.status_code == 200

    events = {event.action for event in db_session.query(AuditEvent).all()}
    assert "transfer.receive" in events
    assert "transfer.shortages.report" in events
    assert "transfer.shortages.resolve" in events
