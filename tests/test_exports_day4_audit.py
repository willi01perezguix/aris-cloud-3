from datetime import date

from app.aris3.db.models import AuditEvent
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_exports_audit_events(client, db_session):
    seed_defaults(db_session)
    _tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-audit")
    token = login(client, user.username, "Pass1234!")
    today = date.today().isoformat()
    payload = {
        "source_type": "reports_daily",
        "format": "csv",
        "filters": {"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
        "transaction_id": "txn-audit-1",
    }
    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "audit-exports"},
        json=payload,
    )
    assert response.status_code == 201
    export_id = response.json()["export_id"]

    download = client.get(
        f"/aris3/exports/{export_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert download.status_code == 200

    events = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.entity_id == export_id)
        .order_by(AuditEvent.created_at.asc())
        .all()
    )
    actions = {event.action for event in events}
    assert "exports.create" in actions
    assert "exports.finalize" in actions
    assert "exports.download" in actions
