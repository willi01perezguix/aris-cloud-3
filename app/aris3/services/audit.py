import logging
from dataclasses import dataclass
from datetime import datetime

from app.aris3.db.models import AuditEvent
from app.aris3.repos.audit import AuditRepository

logger = logging.getLogger(__name__)


@dataclass
class AuditEventPayload:
    tenant_id: str
    user_id: str | None
    store_id: str | None
    trace_id: str | None
    actor: str
    action: str
    entity_type: str | None
    entity_id: str | None
    before: dict | None
    after: dict | None
    metadata: dict | None
    result: str
    actor_role: str | None = None
    effective_tenant_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None


class AuditService:
    """Best-effort audit logging.

    Strategy: failures are logged and swallowed to avoid breaking request flows.
    """

    def __init__(self, db):
        self.repo = AuditRepository(db)

    def record_event(self, payload: AuditEventPayload) -> None:
        metadata = dict(payload.metadata or {})
        metadata.setdefault("actor_role", payload.actor_role)
        metadata.setdefault("effective_tenant_id", payload.effective_tenant_id or payload.tenant_id)
        metadata.setdefault("resource_type", payload.resource_type or payload.entity_type)
        metadata.setdefault("resource_id", payload.resource_id or payload.entity_id)
        try:
            event = AuditEvent(
                tenant_id=payload.tenant_id,
                user_id=payload.user_id,
                store_id=payload.store_id,
                trace_id=payload.trace_id,
                actor=payload.actor,
                action=payload.action,
                entity=payload.entity_type or "unknown",
                entity_type=payload.entity_type or "unknown",
                entity_id=payload.entity_id,
                before_payload=payload.before,
                after_payload=payload.after,
                event_metadata=metadata,
                result=payload.result,
                created_at=datetime.utcnow(),
            )
            self.repo.create(event)
        except Exception:
            logger.exception(
                "Failed to write audit event",
                extra={
                    "action": payload.action,
                    "trace_id": payload.trace_id,
                    "tenant_id": payload.tenant_id,
                    "resource_id": payload.resource_id or payload.entity_id,
                },
            )
