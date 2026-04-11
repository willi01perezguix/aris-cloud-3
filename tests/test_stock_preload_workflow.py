import uuid

from sqlalchemy.exc import ProgrammingError

from app.aris3.routers import stock as stock_router
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


def test_preload_save_rejects_zero_sale_price_without_state_or_stock_side_effects(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "preload-zero-price")
    token = _login(client, user.username, "Pass1234!")
    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "test.xlsx",
            "lines": [{"sku": "SKU-0", "description": "Invalid", "sale_price": "0.00", "qty": 1}],
        },
    )
    assert create.status_code == 201
    line_id = create.json()["lines"][0]["id"]

    save = client.post(f"/aris3/stock/preload-lines/{line_id}/save", headers={"Authorization": f"Bearer {token}"})
    assert save.status_code == 422

    line = client.get(f"/aris3/stock/preload-sessions/{create.json()['id']}", headers={"Authorization": f"Bearer {token}"}).json()["lines"][0]
    assert line["lifecycle_state"] == "STAGING"
    saved_items = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).all()
    assert saved_items == []


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


def test_assign_pending_epc_duplicate_returns_conflict_and_new_epc_succeeds(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "preload-assign-epc")
    token = _login(client, user.username, "Pass1234!")
    existing_epc = "ABCDEFABCDEFABCDEFABC123"
    pending_epc = "ABCDEFABCDEFABCDEFABC456"

    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "test.xlsx",
            "lines": [
                {"sku": "SKU-1", "description": "Jacket", "sale_price": "100.00", "epc": existing_epc, "qty": 1},
                {"sku": "SKU-2", "description": "Pants", "sale_price": "95.00", "qty": 1},
            ],
        },
    )
    line_existing = create.json()["lines"][0]["id"]
    line_pending = create.json()["lines"][1]["id"]
    assert client.post(f"/aris3/stock/preload-lines/{line_existing}/save", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.post(f"/aris3/stock/preload-lines/{line_pending}/save", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    duplicate = client.post(
        f"/aris3/stock/pending-epc/{line_pending}/assign-epc",
        headers={"Authorization": f"Bearer {token}"},
        json={"epc": existing_epc},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "BUSINESS_CONFLICT"
    assert duplicate.json()["details"]["message"] == "epc already active on another in-stock item"
    assert duplicate.json()["details"]["epc"] == existing_epc

    assign_new = client.post(
        f"/aris3/stock/pending-epc/{line_pending}/assign-epc",
        headers={"Authorization": f"Bearer {token}"},
        json={"epc": pending_epc},
    )
    assert assign_new.status_code == 200
    assert assign_new.json()["lifecycle_state"] == "SAVED_EPC_FINAL"

    active = db_session.query(EpcAssignment).filter(EpcAssignment.tenant_id == tenant.id, EpcAssignment.epc == pending_epc, EpcAssignment.active.is_(True)).all()
    assert len(active) == 1


def test_assign_pending_epc_integrity_conflict_maps_to_business_conflict_not_internal_error(client, db_session, monkeypatch):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "preload-assign-epc-integrity")
    token = _login(client, user.username, "Pass1234!")
    duplicate_epc = "ABCDEFABCDEFABCDEFABC888"

    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "integrity-race.xlsx",
            "lines": [
                {"sku": "SKU-EXISTING", "description": "Existing", "sale_price": "120.00", "epc": duplicate_epc, "qty": 1},
                {"sku": "SKU-PENDING", "description": "Pending", "sale_price": "121.00", "qty": 1},
            ],
        },
    )
    line_existing = create.json()["lines"][0]["id"]
    line_pending = create.json()["lines"][1]["id"]
    assert client.post(f"/aris3/stock/preload-lines/{line_existing}/save", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.post(f"/aris3/stock/preload-lines/{line_pending}/save", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    monkeypatch.setattr(stock_router, "_assert_epc_available", lambda *args, **kwargs: None)
    duplicate = client.post(
        f"/aris3/stock/pending-epc/{line_pending}/assign-epc",
        headers={"Authorization": f"Bearer {token}"},
        json={"epc": duplicate_epc},
    )

    assert duplicate.status_code == 409
    payload = duplicate.json()
    assert payload["code"] == "BUSINESS_CONFLICT"
    assert payload["code"] != "INTERNAL_ERROR"
    assert payload["details"]["message"] == "epc already active on another in-stock item"
    assert payload["details"]["epc"] == duplicate_epc


def test_epc_path_regression_save_with_epc_then_duplicate_and_new_assignment(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "preload-epc-shared-path-regression")
    token = _login(client, user.username, "Pass1234!")
    first_epc = "ABCDEFABCDEFABCDEFABC111"
    second_epc = "ABCDEFABCDEFABCDEFABC222"

    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "regression.xlsx",
            "lines": [
                {"sku": "SKU-VERIFY-001", "description": "Invalid price", "sale_price": "0.00", "qty": 1},
                {"sku": "SKU-VERIFY-002", "description": "Pending EPC", "sale_price": "175.00", "qty": 1},
                {"sku": "SKU-VERIFY-003", "description": "With EPC", "sale_price": "185.00", "epc": first_epc, "qty": 1},
            ],
        },
    )
    assert create.status_code == 201
    line_1, line_2, line_3 = [line["id"] for line in create.json()["lines"]]

    save_1 = client.post(f"/aris3/stock/preload-lines/{line_1}/save", headers={"Authorization": f"Bearer {token}"})
    assert save_1.status_code == 422

    save_2 = client.post(f"/aris3/stock/preload-lines/{line_2}/save", headers={"Authorization": f"Bearer {token}"})
    assert save_2.status_code == 200
    assert save_2.json()["lifecycle_state"] == "PENDING_EPC"

    save_3 = client.post(f"/aris3/stock/preload-lines/{line_3}/save", headers={"Authorization": f"Bearer {token}"})
    assert save_3.status_code == 200
    assert save_3.json()["lifecycle_state"] == "SAVED_EPC_FINAL"

    duplicate = client.post(
        f"/aris3/stock/pending-epc/{line_2}/assign-epc",
        headers={"Authorization": f"Bearer {token}"},
        json={"epc": first_epc},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "BUSINESS_CONFLICT"
    assert duplicate.json()["details"]["message"] == "epc already active on another in-stock item"
    assert duplicate.json()["details"]["epc"] == first_epc

    assign_new = client.post(
        f"/aris3/stock/pending-epc/{line_2}/assign-epc",
        headers={"Authorization": f"Bearer {token}"},
        json={"epc": second_epc},
    )
    assert assign_new.status_code == 200
    assert assign_new.json()["lifecycle_state"] == "SAVED_EPC_FINAL"

    assignment_rows = (
        db_session.query(EpcAssignment)
        .filter(EpcAssignment.tenant_id == tenant.id, EpcAssignment.active.is_(True))
        .all()
    )
    assert sorted(row.epc for row in assignment_rows) == [first_epc, second_epc]


def test_superadmin_can_save_and_assign_epc_for_other_tenant_with_explicit_tenant_id(client, db_session):
    run_seed(db_session)
    tenant, store, _user = _create_tenant_user(db_session, "preload-superadmin-cross-tenant")
    superadmin_token = _login(client, "superadmin", "change-me")
    create = client.post(
        f"/aris3/stock/preload-sessions?tenant_id={tenant.id}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
        json={
            "tenant_id": str(tenant.id),
            "store_id": str(store.id),
            "source_file_name": "test.xlsx",
            "lines": [{"sku": "SKU-X", "description": "Cross", "sale_price": "120.00", "qty": 1}],
        },
    )
    assert create.status_code == 201
    line_id = create.json()["lines"][0]["id"]

    save = client.post(
        f"/aris3/stock/preload-lines/{line_id}/save?tenant_id={tenant.id}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert save.status_code == 200
    assert save.json()["tenant_id"] == str(tenant.id)

    assign = client.post(
        f"/aris3/stock/pending-epc/{line_id}/assign-epc?tenant_id={tenant.id}",
        headers={"Authorization": f"Bearer {superadmin_token}"},
        json={"epc": "ABCDEFABCDEFABCDEFABC999"},
    )
    assert assign.status_code == 200
    assert assign.json()["lifecycle_state"] == "SAVED_EPC_FINAL"


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


def test_epc_release_invalid_attempt_returns_conflict(client, db_session):
    run_seed(db_session)
    _tenant, _store, user = _create_tenant_user(db_session, "preload-release-invalid")
    token = _login(client, user.username, "Pass1234!")

    release = client.post(
        "/aris3/stock/epc/release",
        headers={"Authorization": f"Bearer {token}"},
        json={"epc": "222222222222222222222222", "item_uid": str(uuid.uuid4()), "reason": "MANUAL"},
    )
    assert release.status_code == 409
    assert release.json()["code"] == "BUSINESS_CONFLICT"


def test_resolve_issue_requires_item_in_issue_state(client, db_session):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "resolve-issue-conflict")
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
    line = create.json()["lines"][0]
    client.post(f"/aris3/stock/preload-lines/{line['id']}/save", headers={"Authorization": f"Bearer {token}"})

    resolve = client.post(
        f"/aris3/stock/items/{line['item_uid']}/resolve-issue",
        headers={"Authorization": f"Bearer {token}"},
        json={"item_status": "ACTIVE", "observation": "check"},
    )
    assert resolve.status_code == 409
    assert resolve.json()["code"] == "BUSINESS_CONFLICT"


def test_assign_pending_epc_success_does_not_depend_on_refresh_query(client, db_session, monkeypatch):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "preload-assign-refresh-regression")
    token = _login(client, user.username, "Pass1234!")
    pending_epc = "ABCDEFABCDEFABCDEFABCAAA"

    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "refresh-regression.xlsx",
            "lines": [{"sku": "SKU-PENDING", "description": "Pending", "sale_price": "121.00", "qty": 1}],
        },
    )
    line_pending = create.json()["lines"][0]["id"]
    assert client.post(f"/aris3/stock/preload-lines/{line_pending}/save", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    def _raise_refresh(*_args, **_kwargs):
        raise ProgrammingError("SELECT preload_lines", {}, Exception("simulated post-commit refresh failure"))

    monkeypatch.setattr(type(db_session), "refresh", _raise_refresh)

    assign_new = client.post(
        f"/aris3/stock/pending-epc/{line_pending}/assign-epc",
        headers={"Authorization": f"Bearer {token}"},
        json={"epc": pending_epc},
    )

    assert assign_new.status_code == 200
    assert assign_new.json()["lifecycle_state"] == "SAVED_EPC_FINAL"

    active = db_session.query(EpcAssignment).filter(
        EpcAssignment.tenant_id == tenant.id,
        EpcAssignment.epc == pending_epc,
        EpcAssignment.active.is_(True),
    ).all()
    assert len(active) == 1


def test_release_epc_works_with_string_item_uid_lookup(client, db_session):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "preload-release-item-uid-string")
    token = _login(client, user.username, "Pass1234!")
    epc = "333333333333333333333333"

    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "release-string-item-uid.xlsx",
            "lines": [{"sku": "SKU-1", "description": "Jacket", "sale_price": "100.00", "epc": epc, "qty": 1}],
        },
    )
    line_1 = create.json()["lines"][0]
    assert client.post(f"/aris3/stock/preload-lines/{line_1['id']}/save", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    release = client.post(
        "/aris3/stock/epc/release",
        headers={"Authorization": f"Bearer {token}"},
        json={"epc": epc, "item_uid": str(line_1["item_uid"]), "reason": "SOLD"},
    )
    assert release.status_code == 200


def test_assign_pending_epc_requires_previously_saved_pending_line(client, db_session):
    run_seed(db_session)
    _tenant, store, user = _create_tenant_user(db_session, "preload-assign-requires-save")
    token = _login(client, user.username, "Pass1234!")

    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "assign-without-save.xlsx",
            "lines": [{"sku": "SKU-RAW", "description": "Unsaved", "sale_price": "100.00", "qty": 1}],
        },
    )
    assert create.status_code == 201
    line = create.json()["lines"][0]

    assign = client.post(
        f"/aris3/stock/pending-epc/{line['id']}/assign-epc",
        headers={"Authorization": f"Bearer {token}"},
        json={"epc": "ABCDEFABCDEFABCDEFABC777"},
    )
    assert assign.status_code == 409
    payload = assign.json()
    assert payload["code"] == "BUSINESS_CONFLICT"
    assert payload["details"]["message"] == "line must be saved in pending EPC state before assignment"
    assert payload["details"]["lifecycle_state"] == "STAGING"


def test_issue_release_then_resolve_restores_stock_status_and_preserves_preload_snapshot(client, db_session):
    run_seed(db_session)
    tenant, store, user = _create_tenant_user(db_session, "preload-issue-resolve-status")
    token = _login(client, user.username, "Pass1234!")
    epc = "ABCDEFABCDEFABCDEFABC321"

    create = client.post(
        "/aris3/stock/preload-sessions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "store_id": str(store.id),
            "source_file_name": "issue-resolve.xlsx",
            "lines": [{"sku": "SKU-ISSUE", "description": "Issue flow", "sale_price": "100.00", "epc": epc, "qty": 1}],
        },
    )
    assert create.status_code == 201
    line = create.json()["lines"][0]
    assert client.post(f"/aris3/stock/preload-lines/{line['id']}/save", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    mark_issue = client.post(
        f"/aris3/stock/items/{line['item_uid']}/mark-issue",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "issue_state": "DAMAGED",
            "release_epc": True,
            "keep_epc_assigned": False,
            "observation": "released for relabel",
        },
    )
    assert mark_issue.status_code == 200

    resolve_issue = client.post(
        f"/aris3/stock/items/{line['item_uid']}/resolve-issue",
        headers={"Authorization": f"Bearer {token}"},
        json={"item_status": "ACTIVE", "observation": "resolved"},
    )
    assert resolve_issue.status_code == 200

    item = db_session.query(StockItem).filter(StockItem.tenant_id == tenant.id).one()
    assert item.item_status == "ACTIVE"
    assert item.status == "RFID"
    assert item.epc_status == "AVAILABLE"
    assert item.epc is None

    session = client.get(f"/aris3/stock/preload-sessions/{create.json()['id']}", headers={"Authorization": f"Bearer {token}"})
    assert session.status_code == 200
    saved_line = session.json()["lines"][0]
    assert saved_line["lifecycle_state"] == "SAVED_EPC_FINAL"
    assert saved_line["epc"] == epc
    assert saved_line["item_status"] == "ACTIVE"
