from app.aris3.services.audit import AuditEventPayload, AuditService


def test_audit_service_rolls_back_when_write_fails():
    class DummyDB:
        def __init__(self):
            self.rollback_calls = 0

        def rollback(self):
            self.rollback_calls += 1

    db = DummyDB()
    service = AuditService(db)

    def _boom(_event):
        raise RuntimeError("write failed")

    service.repo.create = _boom
    service.record_event(
        AuditEventPayload(
            tenant_id="tenant-1",
            user_id=None,
            store_id=None,
            trace_id="trace-1",
            actor="tester",
            action="test.audit",
            entity_type="test",
            entity_id="entity-1",
            before=None,
            after=None,
            metadata=None,
            result="failure",
        )
    )
    assert db.rollback_calls == 1
