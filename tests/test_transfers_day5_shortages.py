import uuid
from datetime import datetime

from app.aris3.db.models import StockItem, Store, Tenant, TransferMovement, User
from app.aris3.db.seed import run_seed
from app.aris3.core.security import get_password_hash


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
        "transaction_id": "txn-shortage-1",
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


def test_transfer_report_shortages_snapshot(client, db_session):
    run_seed(db_session)
    tenant, origin_store, destination_store, origin_user, destination_user = _create_tenant_users(
        db_session, suffix="shortage"
    )
    origin_token = _login(client, origin_user.username, "Pass1234!")
    dest_token = _login(client, destination_user.username, "Pass1234!")

    epc = "V" * 24
    _seed_stock(db_session, tenant.id, epc=epc, qty=2)

    payload = _transfer_payload(str(origin_store.id), str(destination_store.id), epc, qty=2)
    create_response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "transfer-shortage-1"},
        json=payload,
    )
    assert create_response.status_code == 201
    transfer_id = create_response.json()["header"]["id"]
    lines = create_response.json()["lines"]

    dispatch_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {origin_token}", "Idempotency-Key": "transfer-shortage-2"},
        json={"transaction_id": "txn-shortage-2", "action": "dispatch"},
    )
    assert dispatch_response.status_code == 200

    sku_line = next(line for line in lines if line["line_type"] == "SKU")
    receive_payload = {
        "transaction_id": "txn-shortage-3",
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
        headers={"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-shortage-3"},
        json=receive_payload,
    )
    assert receive_response.status_code == 200

    shortage_payload = {
        "transaction_id": "txn-shortage-4",
        "action": "report_shortages",
        "shortages": [
            {
                "line_id": sku_line["id"],
                "qty": 1,
                "reason_code": "MISSING",
                "notes": "Box damaged",
            }
        ],
    }
    shortage_response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {dest_token}", "Idempotency-Key": "transfer-shortage-4"},
        json=shortage_payload,
    )
    assert shortage_response.status_code == 200

    shortage_line = next(line for line in shortage_response.json()["lines"] if line["line_type"] == "SKU")
    assert shortage_line["shortage_status"] == "REPORTED"

    movement = (
        db_session.query(TransferMovement)
        .filter(TransferMovement.transfer_id == transfer_id, TransferMovement.action == "SHORTAGE_REPORTED")
        .first()
    )
    assert movement is not None
    assert movement.snapshot["reason_code"] == "MISSING"
    assert movement.snapshot["notes"] == "Box damaged"
    assert "line_snapshot" in movement.snapshot
