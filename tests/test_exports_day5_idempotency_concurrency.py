from datetime import date

from app.aris3.db.models import ExportRecord, IdempotencyRecord
from app.aris3.schemas.exports import ExportCreateRequest
from app.aris3.services.idempotency import IdempotencyService
from tests.pos_sales_helpers import create_tenant_user, login, seed_defaults


def test_exports_idempotency_in_progress_blocks_duplicate_artifacts(client, db_session):
    seed_defaults(db_session)
    tenant, store, _other_store, user = create_tenant_user(db_session, suffix="exports-day5-concurrency")
    token = login(client, user.username, "Pass1234!")

    today = date.today().isoformat()
    payload = {
        "source_type": "reports_daily",
        "format": "csv",
        "filters": {"store_id": str(store.id), "from": today, "to": today, "timezone": "UTC"},
        "file_name": None,
        "transaction_id": "txn-export-concurrency",
    }
    request_hash = IdempotencyService.fingerprint(ExportCreateRequest(**payload).model_dump(mode="json"))
    record = IdempotencyRecord(
        tenant_id=tenant.id,
        endpoint="/aris3/exports",
        method="POST",
        idempotency_key="export-concurrency",
        request_hash=request_hash,
        state="in_progress",
        status_code=None,
        response_body=None,
    )
    db_session.add(record)
    db_session.commit()

    before_count = db_session.query(ExportRecord).count()
    response = client.post(
        "/aris3/exports",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "export-concurrency"},
        json=payload,
    )
    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_REQUEST_IN_PROGRESS"
    after_count = db_session.query(ExportRecord).count()
    assert after_count == before_count
