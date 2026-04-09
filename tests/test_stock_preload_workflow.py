import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import EpcAssignment, StockItem, Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_user(db_session, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store {suffix}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=f"user-{suffix}",
        email=f"user-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, store, user])
    db_session.commit()
    return tenant, store, user


def test_preload_save_rejects_missing_sale_price(client, db_session):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "preload-missing-price")
    token = _login(client, user.username, "Pass1234!")
    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "test.xlsx",
            "lines": [{"sku": "SKU-1", "description": "Jacket", "qty": 1}],
        },
    )
    assert create.status_code == 201
    line_id = create.json()["lines"][0]["id"]

    save = client.post(f"/aris3/stock/preload-lines/{line_id}/save", headers={"Authorization": f"Bearer {token}"})
    assert save.status_code == 422


def test_preload_save_to_pending_epc_when_epc_missing(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "preload-pending")
    token = _login(client, user.username, "Pass1234!")
    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "test.xlsx",
            "lines": [{"sku": "SKU-1", "description": "Jacket", "sale_price": "100.00", "qty": 1}],
        },
    )
    line_id = create.json()["lines"][0]["id"]

    save = client.post(f"/aris3/stock/preload-lines/{line_id}/save", headers={"Authorization": f"Bearer {token}"})
    assert save.status_code == 200
    assert save.json()["lifecycle_state"] == "PENDING_EPC"

    saved_items = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).all()
    assert len(saved_items) == 1
    assert saved_items[0].item_status == "PENDING_EPC"


def test_preload_save_to_epc_final_and_conflict(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "preload-epc-conflict")
    token = _login(client, user.username, "Pass1234!")
    epc = "ABCDEFABCDEFABCDEFABCDEF"

    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "test.xlsx",
            "lines": [
                {"sku": "SKU-1", "description": "Jacket", "sale_price": "100.00", "epc": epc, "qty": 1},
                {"sku": "SKU-2", "description": "Pants", "sale_price": "90.00", "epc": epc, "qty": 1},
            ],
        },
    )
    line_1 = create.json()["lines"][0]["id"]
    line_2 = create.json()["lines"][1]["id"]

    save_1 = client.post(f"/aris3/stock/preload-lines/{line_1}/save", headers={"Authorization": f"Bearer {token}"})
    assert save_1.status_code == 200
    assert save_1.json()["lifecycle_state"] == "SAVED_EPC_FINAL"

    save_2 = client.post(f"/aris3/stock/preload-lines/{line_2}/save", headers={"Authorization": f"Bearer {token}"})
    assert save_2.status_code == 409
    assert save_2.json()["code"] == "BUSINESS_CONFLICT"

    assignments = db_session.query(EpcAssignment).filter(EpcAssignment.tenant_id == tenant.id, EpcAssignment.epc == epc).all()
    assert len(assignments) == 1
    assert assignments[0].active is True


def test_epc_release_and_reuse(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "preload-release-reuse")
    token = _login(client, user.username, "Pass1234!")
    epc = "111111111111111111111111"

    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "test.xlsx",
            "lines": [{"sku": "SKU-1", "description": "Jacket", "sale_price": "100.00", "epc": epc, "qty": 1}],
        },
    )
    line_1 = create.json()["lines"][0]
    client.post(f"/aris3/stock/preload-lines/{line_1['id']}/save", headers={"Authorization": f"Bearer {token}"})

    release = client.post(
        "/aris3/stock/epc/release",
        headers={"Authorization": f"Bearer {token}"},
        json={"epc": epc, "item_uid": line_1["item_uid"], "reason": "SOLD"},
    )
    assert release.status_code == 200

    create_2 = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "test2.xlsx",
            "lines": [{"sku": "SKU-2", "description": "Pants", "sale_price": "110.00", "epc": epc, "qty": 1}],
        },
    )
    line_2 = create_2.json()["lines"][0]["id"]
    save_2 = client.post(f"/aris3/stock/preload-lines/{line_2}/save", headers={"Authorization": f"Bearer {token}"})
    assert save_2.status_code == 200

    active = db_session.query(EpcAssignment).filter(EpcAssignment.tenant_id == tenant.id, EpcAssignment.epc == epc, EpcAssignment.active.is_(True)).all()
    assert len(active) == 1
