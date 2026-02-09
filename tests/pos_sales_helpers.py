from __future__ import annotations

import uuid
from datetime import datetime

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import PosCashSession, StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed


def login(client, username: str, password: str) -> str:
    response = client.post(
        "/aris3/auth/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def create_tenant_user(db_session, *, suffix: str, role: str = "ADMIN"):
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


def seed_defaults(db_session):
    run_seed(db_session)


def create_stock_item(
    db_session,
    *,
    tenant_id: str,
    sku: str | None,
    epc: str | None,
    location_code: str,
    pool: str,
    status: str,
    location_is_vendible: bool = True,
):
    stock = StockItem(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        sku=sku,
        description="Item",
        var1_value="V1",
        var2_value="V2",
        epc=epc,
        location_code=location_code,
        pool=pool,
        status=status,
        location_is_vendible=location_is_vendible,
        image_asset_id=uuid.uuid4(),
        image_url="https://example.com/img.png",
        image_thumb_url="https://example.com/thumb.png",
        image_source="catalog",
        image_updated_at=datetime.utcnow(),
    )
    db_session.add(stock)
    db_session.commit()
    return stock


def open_cash_session(
    db_session,
    *,
    tenant_id: str,
    store_id: str,
    cashier_user_id: str,
    opening_amount: float = 100.0,
    business_date: datetime | None = None,
    timezone: str = "UTC",
):
    if business_date is None:
        business_date = datetime.utcnow()
    session = PosCashSession(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        store_id=store_id,
        cashier_user_id=cashier_user_id,
        status="OPEN",
        business_date=business_date.date(),
        timezone=timezone,
        opening_amount=opening_amount,
        expected_cash=opening_amount,
        opened_at=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.commit()
    return session


def sale_line(
    *,
    line_type: str,
    qty: int,
    unit_price: float,
    sku: str | None,
    epc: str | None,
    location_code: str = "LOC-1",
    pool: str = "P1",
    status: str = "RFID",
):
    return {
        "line_type": line_type,
        "qty": qty,
        "unit_price": unit_price,
        "snapshot": {
            "sku": sku,
            "description": "Item",
            "var1_value": "V1",
            "var2_value": "V2",
            "epc": epc,
            "location_code": location_code,
            "pool": pool,
            "status": status,
            "location_is_vendible": True,
            "image_asset_id": str(uuid.uuid4()),
            "image_url": "https://example.com/img.png",
            "image_thumb_url": "https://example.com/thumb.png",
            "image_source": "catalog",
            "image_updated_at": datetime.utcnow().isoformat(),
        },
    }


def sale_payload(store_id: str, lines: list[dict], *, transaction_id: str = "txn-1"):
    return {"transaction_id": transaction_id, "store_id": store_id, "lines": lines}


def set_return_policy(client, token: str, payload: dict, *, idempotency_key: str = "return-policy-1"):
    response = client.patch(
        "/aris3/admin/settings/return-policy",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        json=payload,
    )
    assert response.status_code == 200
    return response.json()


def create_paid_sale(
    client,
    token: str,
    store_id: str,
    lines: list[dict],
    payments: list[dict],
    *,
    create_txn: str = "txn-sale-create",
    checkout_txn: str = "txn-sale-checkout",
    idempotency_key: str = "sale-create",
    checkout_idempotency_key: str = "sale-checkout",
):
    create_response = client.post(
        "/aris3/pos/sales",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        json=sale_payload(store_id, lines, transaction_id=create_txn),
    )
    assert create_response.status_code == 201
    sale_id = create_response.json()["header"]["id"]

    checkout_payload = {
        "transaction_id": checkout_txn,
        "action": "checkout",
        "payments": payments,
    }
    checkout_response = client.post(
        f"/aris3/pos/sales/{sale_id}/actions",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": checkout_idempotency_key},
        json=checkout_payload,
    )
    assert checkout_response.status_code == 200
    return checkout_response.json()
