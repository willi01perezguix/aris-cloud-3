import uuid

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import Store, Tenant, User
from app.aris3.db.seed import run_seed


def _login(client, username: str, password: str) -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_with_two_stores(db_session, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant {suffix}")
    store_a = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"StoreA {suffix}")
    store_b = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"StoreB {suffix}")
    user_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store_a.id,
        username=f"user-a-{suffix}",
        email=f"user-a-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="ADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    user_b = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store_b.id,
        username=f"user-b-{suffix}",
        email=f"user-b-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="USER",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db_session.add_all([tenant, store_a, store_b, user_a, user_b])
    db_session.commit()
    return tenant, store_a, store_b, user_a, user_b


def _create_pending_line(client, token: str, store_id: str, sku: str) -> str:
    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": store_id,
            "source_file_name": "pending-epc-scope.xlsx",
            "lines": [{"sku": sku, "description": "Pending EPC", "sale_price": "125.00", "qty": 1}],
        },
    )
    assert create.status_code == 201
    line_id = create.json()["lines"][0]["id"]
    save = client.post(f"/aris3/stock/preload-lines/{line_id}/save", headers={"Authorization": f"Bearer {token}"})
    assert save.status_code == 200
    assert save.json()["lifecycle_state"] == "PENDING_EPC"
    return line_id


def test_pending_epc_list_and_assign_are_store_scoped(client, db_session):
    run_seed(db_session)
    _tenant, store_a, store_b, user_a, user_b = _create_tenant_with_two_stores(db_session, "pending-epc-scope")

    token_a = _login(client, user_a.username, "Pass1234!")
    token_b = _login(client, user_b.username, "Pass1234!")

    line_a = _create_pending_line(client, token_a, str(store_a.id), "SKU-STORE-A")
    line_b = _create_pending_line(client, token_a, str(store_b.id), "SKU-STORE-B")

    listed_default = client.get("/aris3/stock/pending-epc", headers={"Authorization": f"Bearer {token_b}"})
    assert listed_default.status_code == 200
    ids_default = {row["id"] for row in listed_default.json()}
    assert line_b in ids_default
    assert line_a not in ids_default
    assert {row["store_id"] for row in listed_default.json()} == {str(store_b.id)}

    listed_own_store = client.get(
        f"/aris3/stock/pending-epc?store_id={store_b.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert listed_own_store.status_code == 200
    assert {row["id"] for row in listed_own_store.json()} == {line_b}

    listed_other_store = client.get(
        f"/aris3/stock/pending-epc?store_id={store_a.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert listed_other_store.status_code == 403

    assign_own = client.post(
        f"/aris3/stock/pending-epc/{line_b}/assign-epc",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"epc": "ABCDEFABCDEFABCDEFABC101"},
    )
    assert assign_own.status_code == 200
    assert assign_own.json()["lifecycle_state"] == "SAVED_EPC_FINAL"

    assign_other_store = client.post(
        f"/aris3/stock/pending-epc/{line_a}/assign-epc",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"epc": "ABCDEFABCDEFABCDEFABC102"},
    )
    assert assign_other_store.status_code == 403

    assign_admin_other_store = client.post(
        f"/aris3/stock/pending-epc/{line_b}/assign-epc",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"epc": "ABCDEFABCDEFABCDEFABC103"},
    )
    assert assign_admin_other_store.status_code == 403


def test_pending_epc_tenant_scope_requires_explicit_scope_parameter(client, db_session):
    run_seed(db_session)
    tenant, store_a, store_b, user_a, _user_b = _create_tenant_with_two_stores(db_session, "pending-epc-tenant-scope")
    token_a = _login(client, user_a.username, "Pass1234!")

    line_a = _create_pending_line(client, token_a, str(store_a.id), "SKU-TS-A")
    line_b = _create_pending_line(client, token_a, str(store_b.id), "SKU-TS-B")

    listed_default = client.get(
        f"/aris3/stock/pending-epc?tenant_id={tenant.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert listed_default.status_code == 200
    assert {row["id"] for row in listed_default.json()} == {line_a}
    assert {row["store_id"] for row in listed_default.json()} == {str(store_a.id)}

    listed_explicit_tenant_scope = client.get(
        f"/aris3/stock/pending-epc?tenant_id={tenant.id}&scope=tenant",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert listed_explicit_tenant_scope.status_code == 200
    assert {row["id"] for row in listed_explicit_tenant_scope.json()} == {line_a, line_b}


def test_pending_epc_openapi_documents_store_id_query_param(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/aris3/stock/pending-epc"]["get"]
    parameter_names = {parameter["name"] for parameter in operation.get("parameters", [])}

    assert "store_id" in parameter_names
    assert "scope" in parameter_names
