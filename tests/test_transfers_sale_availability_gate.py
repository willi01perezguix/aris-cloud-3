import uuid
from datetime import datetime

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed
from tests.pos_sales_helpers import sale_line, sale_payload


def _login(client, username: str, password: str = "Pass1234!") -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _bootstrap(db_session, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    origin_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Origin {suffix}")
    destination_store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Destination {suffix}")
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
    db_session.add_all([tenant, origin_store, destination_store, origin_user, destination_user])
    db_session.commit()
    return tenant, origin_store, destination_store, origin_user, destination_user


def _seed_epc_stock(db_session, *, tenant_id, store_id, epc: str):
    db_session.add(
        StockItem(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            store_id=store_id,
            sku="SKU-EPC",
            description="Transfer EPC item",
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
    )
    db_session.commit()


def _seed_sku_stock(db_session, *, tenant_id, store_id, sku: str, qty: int):
    for _ in range(qty):
        db_session.add(
            StockItem(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                store_id=store_id,
                sku=sku,
                description="Transfer SKU item",
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


def _create_transfer(client, token: str, payload: dict, idempotency_key: str):
    response = client.post(
        "/aris3/transfers",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


def _dispatch_transfer(client, token: str, transfer_id: str, tx: str, idempotency_key: str):
    response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        json={"transaction_id": tx, "action": "dispatch"},
    )
    assert response.status_code == 200


def _receive_transfer(client, token: str, transfer_id: str, line_id: str, qty: int, tx: str, idempotency_key: str):
    response = client.post(
        f"/aris3/transfers/{transfer_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        json={
            "transaction_id": tx,
            "action": "receive",
            "receive_lines": [{"line_id": line_id, "qty": qty, "location_code": "DEST-1", "pool": "SALE"}],
        },
    )
    assert response.status_code == 200


def _create_sale(client, token: str, store_id: str, transaction_id: str, line: dict):
    return client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"sale-{transaction_id}"},
        json=sale_payload(store_id, [line], transaction_id=transaction_id),
    )


def test_epc_not_sellable_at_destination_until_received(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, origin_user, destination_user = _bootstrap(db_session, "availability-epc")
    origin_token = _login(client, origin_user.username)
    destination_token = _login(client, destination_user.username)
    epc = "AVAIL" + "1" * 19
    _seed_epc_stock(db_session, tenant_id=tenant.id, store_id=origin.id, epc=epc)

    payload = {
        "transaction_id": "txn-epc-create",
        "origin_store_id": str(origin.id),
        "destination_store_id": str(destination.id),
        "lines": [
            {
                "line_type": "EPC",
                "qty": 1,
                "snapshot": {
                    "sku": "SKU-EPC",
                    "description": "Transfer EPC item",
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
    transfer = _create_transfer(client, origin_token, payload, "availability-epc-create")
    transfer_id = transfer["header"]["id"]
    line_id = transfer["lines"][0]["id"]

    _dispatch_transfer(client, origin_token, transfer_id, "txn-epc-dispatch", "availability-epc-dispatch")

    pre_receive_sale = _create_sale(
        client,
        destination_token,
        str(destination.id),
        "txn-epc-sale-pre-receive",
        sale_line(line_type="EPC", qty=1, unit_price=None, sku="SKU-EPC", epc=epc, status="RFID"),
    )
    assert pre_receive_sale.status_code == 422

    _receive_transfer(client, destination_token, transfer_id, line_id, 1, "txn-epc-receive", "availability-epc-receive")

    post_receive_sale = _create_sale(
        client,
        destination_token,
        str(destination.id),
        "txn-epc-sale-post-receive",
        sale_line(line_type="EPC", qty=1, unit_price=None, sku="SKU-EPC", epc=epc, status="RFID"),
    )
    assert post_receive_sale.status_code == 201


def test_sku_not_sellable_at_destination_until_received(client, db_session):
    run_seed(db_session)
    tenant, origin, destination, origin_user, destination_user = _bootstrap(db_session, "availability-sku")
    origin_token = _login(client, origin_user.username)
    destination_token = _login(client, destination_user.username)
    _seed_sku_stock(db_session, tenant_id=tenant.id, store_id=origin.id, sku="SKU-PENDING", qty=2)

    payload = {
        "transaction_id": "txn-sku-create",
        "origin_store_id": str(origin.id),
        "destination_store_id": str(destination.id),
        "lines": [
            {
                "line_type": "SKU",
                "qty": 2,
                "snapshot": {
                    "sku": "SKU-PENDING",
                    "description": "Transfer SKU item",
                    "var1_value": "Blue",
                    "var2_value": "L",
                    "epc": None,
                    "location_code": "LOC-1",
                    "pool": "P1",
                    "status": "PENDING",
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
    transfer = _create_transfer(client, origin_token, payload, "availability-sku-create")
    transfer_id = transfer["header"]["id"]
    line_id = transfer["lines"][0]["id"]

    _dispatch_transfer(client, origin_token, transfer_id, "txn-sku-dispatch", "availability-sku-dispatch")

    pre_receive_sale = _create_sale(
        client,
        destination_token,
        str(destination.id),
        "txn-sku-sale-pre-receive",
        sale_line(line_type="SKU", qty=1, unit_price=None, sku="SKU-PENDING", epc=None, status="PENDING"),
    )
    assert pre_receive_sale.status_code == 422

    _receive_transfer(client, destination_token, transfer_id, line_id, 2, "txn-sku-receive", "availability-sku-receive")

    post_receive_sale = _create_sale(
        client,
        destination_token,
        str(destination.id),
        "txn-sku-sale-post-receive",
        sale_line(line_type="SKU", qty=2, unit_price=None, sku="SKU-PENDING", epc=None, status="PENDING"),
    )
    assert post_receive_sale.status_code == 201
