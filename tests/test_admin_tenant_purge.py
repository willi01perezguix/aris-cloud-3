import uuid
from datetime import date

from app.aris3.core.security import get_password_hash
from app.aris3.db.models import (
    AuditEvent,
    ExportRecord,
    PosCashDayClose,
    PosCashMovement,
    PosCashSession,
    PosPayment,
    PosReturnEvent,
    PosSale,
    PosSaleLine,
    StockItem,
    Store,
    Tenant,
    Transfer,
    TransferLine,
    TransferMovement,
    User,
)
from app.aris3.db.seed import run_seed
from app.aris3.services.tenant_purge import TenantPurgeService


def _login(client, username: str, password: str) -> str:
    response = client.post("/aris3/auth/login", json={"username_or_email": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_tenant_store_user(db_session, *, suffix: str):
    tenant = Tenant(id=uuid.uuid4(), name=f"Tenant Purge {suffix}")
    store = Store(id=uuid.uuid4(), tenant_id=tenant.id, name=f"Store Purge {suffix}")
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        username=f"purge-user-{suffix}",
        email=f"purge-user-{suffix}@example.com",
        hashed_password=get_password_hash("Pass1234!"),
        role="USER",
        status="ACTIVE",
        is_active=True,
        must_change_password=False,
    )
    db_session.add_all([tenant, store, user])
    db_session.commit()
    return tenant, store, user


def _seed_operational_data(db_session, *, tenant, store, user):
    transfer = Transfer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        origin_store_id=store.id,
        destination_store_id=store.id,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
        status="RECEIVED",
    )
    transfer_canceled = Transfer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        origin_store_id=store.id,
        destination_store_id=store.id,
        created_by_user_id=user.id,
        canceled_by_user_id=user.id,
        status="CANCELED",
    )
    db_session.add_all([transfer, transfer_canceled])
    db_session.flush()

    transfer_line = TransferLine(id=uuid.uuid4(), transfer_id=transfer.id, tenant_id=tenant.id, line_type="EPC", qty=1)
    db_session.add(transfer_line)
    db_session.flush()
    db_session.add(
        TransferMovement(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            transfer_id=transfer.id,
            transfer_line_id=transfer_line.id,
            action="RECEIVE",
            qty=1,
        )
    )

    sale = PosSale(id=uuid.uuid4(), tenant_id=tenant.id, store_id=store.id, status="CHECKED_OUT", total_due=20.0, paid_total=20.0, balance_due=0.0)
    db_session.add(sale)
    db_session.flush()
    db_session.add(PosSaleLine(id=uuid.uuid4(), sale_id=sale.id, tenant_id=tenant.id, line_type="ITEM", qty=1, unit_price=20.0, line_total=20.0))
    db_session.add(PosPayment(id=uuid.uuid4(), sale_id=sale.id, tenant_id=tenant.id, method="CASH", amount=20.0))
    db_session.add(PosReturnEvent(id=uuid.uuid4(), tenant_id=tenant.id, store_id=store.id, sale_id=sale.id, action="REFUND"))

    cash_session = PosCashSession(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        store_id=store.id,
        cashier_user_id=user.id,
        business_date=date.today(),
        status="CLOSED",
    )
    db_session.add(cash_session)
    db_session.flush()
    db_session.add(
        PosCashMovement(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            store_id=store.id,
            cash_session_id=cash_session.id,
            cashier_user_id=user.id,
            business_date=date.today(),
            action="SALE_CASH_IN",
            amount=20.0,
        )
    )
    db_session.add(
        PosCashDayClose(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            store_id=store.id,
            business_date=date.today(),
            closed_by_user_id=user.id,
        )
    )

    db_session.add(ExportRecord(id=uuid.uuid4(), tenant_id=tenant.id, store_id=store.id, source_type="sales", format="csv", filters_snapshot={}))
    db_session.add(StockItem(id=uuid.uuid4(), tenant_id=tenant.id, store_id=store.id, sku=f"SKU-{uuid.uuid4()}"))
    db_session.commit()


def _purge_request(client, token: str, tenant_id: str, idempotency_key: str, *, dry_run: bool, preserve_audit_events: bool = True, reason: str = "cleanup"):
    return client.post(
        f"/aris3/admin/tenants/{tenant_id}/purge",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        json={
            "confirm": f"PURGE {tenant_id}",
            "dry_run": dry_run,
            "preserve_audit_events": preserve_audit_events,
            "reason": reason,
        },
    )


def _store_purge_request(client, token: str, store_id: str, idempotency_key: str, *, dry_run: bool, preserve_audit_events: bool = True):
    return client.post(
        f"/aris3/admin/stores/{store_id}/purge",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        json={"confirm": f"PURGE {store_id}", "dry_run": dry_run, "preserve_audit_events": preserve_audit_events, "reason": "cleanup store"},
    )


def _user_purge_request(client, token: str, user_id: str, idempotency_key: str, *, dry_run: bool, preserve_audit_events: bool = True):
    return client.post(
        f"/aris3/admin/users/{user_id}/purge",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        json={"confirm": f"PURGE {user_id}", "dry_run": dry_run, "preserve_audit_events": preserve_audit_events, "reason": "cleanup user"},
    )


def test_tenant_purge_dry_run_reports_exact_counts_without_deleting(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="dry-run")
    _seed_operational_data(db_session, tenant=tenant, store=store, user=user)

    response = _purge_request(client, token, str(tenant.id), "purge-dry-run-1", dry_run=True)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "DRY_RUN"
    assert payload["would_delete_counts"]["tenants"] == 1
    assert payload["would_delete_counts"]["transfers"] >= 2
    assert payload["deleted_counts"] is None

    db_session.expire_all()
    assert db_session.get(Tenant, str(tenant.id)) is not None


def test_tenant_purge_confirm_mismatch_returns_422(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, _store, _user = _create_tenant_store_user(db_session, suffix="confirm")

    response = client.post(
        f"/aris3/admin/tenants/{tenant.id}/purge",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "purge-confirm-1"},
        json={"confirm": "PURGE WRONG", "dry_run": True, "preserve_audit_events": True},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_tenant_purge_requires_idempotency_key(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, _store, _user = _create_tenant_store_user(db_session, suffix="missing-idem")

    response = client.post(
        f"/aris3/admin/tenants/{tenant.id}/purge",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirm": f"PURGE {tenant.id}", "dry_run": True, "preserve_audit_events": True},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_tenant_purge_is_idempotent_for_same_payload_and_key(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, _store, _user = _create_tenant_store_user(db_session, suffix="idem-replay")

    first = _purge_request(client, token, str(tenant.id), "purge-idem-replay-1", dry_run=True)
    second = _purge_request(client, token, str(tenant.id), "purge-idem-replay-1", dry_run=True)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert second.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"


def test_tenant_purge_reused_key_with_different_payload_conflicts(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, _store, _user = _create_tenant_store_user(db_session, suffix="idem-conflict")

    first = _purge_request(client, token, str(tenant.id), "purge-idem-conflict-1", dry_run=True)
    assert first.status_code == 200

    second = _purge_request(client, token, str(tenant.id), "purge-idem-conflict-1", dry_run=False)
    assert second.status_code == 409
    assert second.json()["code"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"


def test_tenant_purge_real_delete_removes_received_and_canceled_transfer_history(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="real-delete")
    tenant_id = str(tenant.id)
    _seed_operational_data(db_session, tenant=tenant, store=store, user=user)

    response = _purge_request(client, token, tenant_id, "purge-real-1", dry_run=False)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert payload["deleted_counts"]["tenants"] == 1
    assert payload["deleted_counts"]["transfers"] >= 2

    db_session.expire_all()
    assert db_session.get(Tenant, tenant_id) is None


def test_tenant_purge_preserve_audit_events_true_keeps_audit_history(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, _store, _user = _create_tenant_store_user(db_session, suffix="audit-preserve")
    tenant_id = str(tenant.id)
    db_session.add(
        AuditEvent(
            tenant_id=tenant.id,
            actor="seed",
            action="manual.seed",
            entity="tenant",
            entity_type="tenant",
            entity_id=tenant_id,
            result="success",
        )
    )
    db_session.commit()

    response = _purge_request(client, token, tenant_id, "purge-audit-preserve-1", dry_run=False, preserve_audit_events=True)
    assert response.status_code == 200

    db_session.expire_all()
    preserved = db_session.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id).all()
    assert preserved


def test_delete_tenant_safe_delete_still_blocks_historical_dependencies_after_purge_feature(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="safe-delete")
    transfer = Transfer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        origin_store_id=store.id,
        destination_store_id=store.id,
        created_by_user_id=user.id,
        status="RECEIVED",
    )
    db_session.add(transfer)
    db_session.commit()

    response = client.delete(
        f"/aris3/admin/tenants/{tenant.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "safe-delete-tenant-1"},
    )
    assert response.status_code == 409
    assert response.json()["message"] == "Cannot delete tenant with active dependencies"


def test_delete_store_user_endpoints_keep_existing_safe_delete_behavior(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="store-user-reg")

    store_conflict = client.delete(
        f"/aris3/admin/stores/{store.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "safe-delete-store-1"},
    )
    assert store_conflict.status_code == 409

    transfer = Transfer(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        origin_store_id=store.id,
        destination_store_id=store.id,
        created_by_user_id=user.id,
    )
    db_session.add(transfer)
    db_session.commit()

    user_conflict = client.delete(
        f"/aris3/admin/users/{user.id}",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "safe-delete-user-1"},
    )
    assert user_conflict.status_code == 409


def test_tenant_purge_failure_releases_lock_and_allows_retry(client, db_session, monkeypatch):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="retry")
    tenant_id = str(tenant.id)
    _seed_operational_data(db_session, tenant=tenant, store=store, user=user)

    original_delete = TenantPurgeService._delete_tenant_in_order
    state = {"failed": False}

    def _boom_once(self, *, tenant_id: str, preserve_audit_events: bool):
        if not state["failed"]:
            state["failed"] = True
            raise RuntimeError("simulated purge failure")
        return original_delete(self, tenant_id=tenant_id, preserve_audit_events=preserve_audit_events)

    monkeypatch.setattr(TenantPurgeService, "_delete_tenant_in_order", _boom_once)

    first = _purge_request(client, token, tenant_id, "purge-retry-1", dry_run=False)
    assert first.status_code == 500

    second = _purge_request(client, token, tenant_id, "purge-retry-2", dry_run=False)
    assert second.status_code == 200
    assert second.json()["status"] == "COMPLETED"


def test_store_purge_dry_run_reports_counts(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="store-dry")
    _seed_operational_data(db_session, tenant=tenant, store=store, user=user)
    response = _store_purge_request(client, token, str(store.id), "store-purge-dry-1", dry_run=True)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRY_RUN"
    assert body["would_delete_counts"]["stores"] == 1
    assert body["would_delete_counts"]["transfer_movements"] >= 1
    assert body["would_delete_counts"]["transfer_lines"] >= 1
    assert body["would_delete_counts"]["sale_lines"] >= 1
    assert body["would_delete_counts"]["payments"] >= 1
    assert body["would_delete_counts"]["user_permission_overrides"] >= 0
    assert body["would_delete_counts"]["transfers"] >= 1
    assert body["deleted_counts"] is None


def test_user_purge_dry_run_reports_counts(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="user-dry")
    _seed_operational_data(db_session, tenant=tenant, store=store, user=user)
    response = _user_purge_request(client, token, str(user.id), "user-purge-dry-1", dry_run=True)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRY_RUN"
    assert body["would_delete_counts"]["users"] == 1
    assert body["would_delete_counts"]["transfers_as_creator"] >= 1


def test_user_purge_dry_run_does_not_acquire_db_lock(client, db_session, monkeypatch):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="user-dry-no-lock")
    _seed_operational_data(db_session, tenant=tenant, store=store, user=user)

    def _forbidden_lock(*args, **kwargs):  # pragma: no cover - defensive sentinel
        raise AssertionError("dry_run must not acquire purge DB lock")

    monkeypatch.setattr(TenantPurgeService, "_acquire_lock", _forbidden_lock)
    response = _user_purge_request(client, token, str(user.id), "user-purge-dry-no-lock-1", dry_run=True)
    assert response.status_code == 200
    assert response.json()["status"] == "DRY_RUN"


def test_store_purge_invalid_confirm_returns_422(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    _tenant, store, _user = _create_tenant_store_user(db_session, suffix="store-confirm")
    response = client.post(
        f"/aris3/admin/stores/{store.id}/purge",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "store-confirm-1"},
        json={"confirm": "PURGE WRONG", "dry_run": True, "preserve_audit_events": True},
    )
    assert response.status_code == 422


def test_store_purge_requires_idempotency_key(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    _tenant, store, _user = _create_tenant_store_user(db_session, suffix="store-idem-required")
    response = client.post(
        f"/aris3/admin/stores/{store.id}/purge",
        headers={"Authorization": f"Bearer {token}"},
        json={"confirm": f"PURGE {store.id}", "dry_run": True, "preserve_audit_events": True},
    )
    assert response.status_code == 422


def test_store_purge_idempotency_replay_and_conflict(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    _tenant, store, _user = _create_tenant_store_user(db_session, suffix="store-idem")
    first = _store_purge_request(client, token, str(store.id), "store-idem-1", dry_run=True)
    second = _store_purge_request(client, token, str(store.id), "store-idem-1", dry_run=True)
    third = _store_purge_request(client, token, str(store.id), "store-idem-1", dry_run=False)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.headers.get("X-Idempotency-Result") == "IDEMPOTENCY_REPLAY"
    assert third.status_code == 409


def test_store_purge_real_delete_works_with_historical_terminal_data(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="store-real")
    _seed_operational_data(db_session, tenant=tenant, store=store, user=user)
    store_id = str(store.id)
    response = _store_purge_request(client, token, store_id, "store-real-1", dry_run=False)
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    assert response.json()["deleted_counts"]["transfer_movements"] >= 1
    assert response.json()["deleted_counts"]["transfer_lines"] >= 1
    assert response.json()["deleted_counts"]["sale_lines"] >= 1
    assert response.json()["deleted_counts"]["payments"] >= 1
    db_session.expire_all()
    assert db_session.get(Store, store_id) is None


def test_store_purge_preserve_audit_events_true_keeps_store_audit_history(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="store-audit")
    db_session.add(
        AuditEvent(
            tenant_id=tenant.id,
            store_id=store.id,
            actor="seed",
            action="manual.store.audit",
            entity="store",
            entity_type="store",
            entity_id=str(store.id),
            result="success",
        )
    )
    db_session.commit()
    response = _store_purge_request(client, token, str(store.id), "store-audit-keep-1", dry_run=False, preserve_audit_events=True)
    assert response.status_code == 200
    remaining = db_session.query(AuditEvent).filter(AuditEvent.store_id == store.id).all()
    assert any(ev.action == "manual.store.audit" for ev in remaining)


def test_user_purge_real_delete_nullifies_transfer_actor_refs(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="user-real")
    _seed_operational_data(db_session, tenant=tenant, store=store, user=user)
    user_id = str(user.id)
    response = _user_purge_request(client, token, user_id, "user-real-1", dry_run=False)
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"
    db_session.expire_all()
    assert db_session.get(User, user_id) is None
    transfers = db_session.query(Transfer).filter(Transfer.tenant_id == tenant.id).all()
    assert transfers
    assert all(t.created_by_user_id is None for t in transfers)


def test_purge_response_contains_trace_and_audit_events(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    _tenant, store, _user = _create_tenant_store_user(db_session, suffix="trace-audit")
    response = _store_purge_request(client, token, str(store.id), "store-trace-1", dry_run=True, preserve_audit_events=True)
    assert response.status_code == 200
    trace_id = response.json()["trace_id"]
    assert trace_id
    events = db_session.query(AuditEvent).filter(AuditEvent.trace_id == trace_id, AuditEvent.action.like("admin.store.purge.%")).all()
    assert any(e.action.endswith(".started") for e in events)
    assert any(e.action.endswith(".completed") for e in events)


def test_user_purge_preserve_audit_events_respected(client, db_session):
    run_seed(db_session)
    token = _login(client, "superadmin", "change-me")
    tenant, store, user = _create_tenant_store_user(db_session, suffix="user-audit")
    db_session.add(
        AuditEvent(
            tenant_id=tenant.id,
            user_id=user.id,
            actor="seed",
            action="manual.user.audit",
            entity="user",
            entity_type="user",
            entity_id=str(user.id),
            result="success",
        )
    )
    db_session.commit()
    response = _user_purge_request(client, token, str(user.id), "user-audit-1", dry_run=False, preserve_audit_events=False)
    assert response.status_code == 200
    remaining = db_session.query(AuditEvent).filter(AuditEvent.user_id == user.id).all()
    assert all(ev.action.startswith("admin.user.purge.") for ev in remaining)
