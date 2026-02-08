from app.aris3.db.models import AuditEvent


class AuditRepository:
    def __init__(self, db):
        self.db = db

    def create(self, event: AuditEvent) -> AuditEvent:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
