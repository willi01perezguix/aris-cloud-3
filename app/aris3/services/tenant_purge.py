from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.aris3.core.error_catalog import AppError, ErrorCatalog
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
    ReturnPolicySettings,
    RoleTemplate,
    RoleTemplatePermission,
    StockItem,
    Store,
    StoreRolePolicy,
    Tenant,
    TenantPurgeLock,
    TenantRolePolicy,
    Transfer,
    TransferLine,
    TransferMovement,
    User,
    UserPermissionOverride,
    VariantFieldSettings,
)
from app.aris3.services.audit import AuditEventPayload, AuditService


PURGE_ORDER = (
    ("transfer_movements", TransferMovement),
    ("transfer_lines", TransferLine),
    ("transfers", Transfer),
    ("sale_lines", PosSaleLine),
    ("payments", PosPayment),
    ("returns", PosReturnEvent),
    ("sales", PosSale),
    ("cash_movements", PosCashMovement),
    ("cash_sessions", PosCashSession),
    ("cash_day_closes", PosCashDayClose),
    ("exports", ExportRecord),
    ("stock_items", StockItem),
    ("user_permission_overrides", UserPermissionOverride),
    ("store_role_policies", StoreRolePolicy),
    ("tenant_role_policies", TenantRolePolicy),
    ("users", User),
    ("stores", Store),
    ("tenants", Tenant),
)


@dataclass
class TenantPurgeResult:
    dry_run: bool
    status: str
    counts: dict[str, int]


class TenantPurgeService:
    def __init__(self, db):
        self.db = db
        self.audit = AuditService(db)

    def execute(
        self,
        *,
        tenant_id: str,
        actor,
        reason: str | None,
        dry_run: bool,
        preserve_audit_events: bool,
        trace_id: str | None,
    ) -> TenantPurgeResult:
        tenant = self.db.get(Tenant, tenant_id)
        if tenant is None:
            raise AppError(ErrorCatalog.TENANT_NOT_FOUND)

        lock = self._acquire_lock(tenant_id=tenant_id, trace_id=trace_id)
        try:
            self._audit_started(
                tenant_id=tenant_id,
                actor=actor,
                reason=reason,
                dry_run=dry_run,
                preserve_audit_events=preserve_audit_events,
                trace_id=trace_id,
            )
            counts = self._counts(tenant_id=tenant_id)
            counts["tenants"] = 1
            if dry_run:
                self._audit_completed(
                    tenant_id=tenant_id,
                    actor=actor,
                    reason=reason,
                    dry_run=True,
                    preserve_audit_events=preserve_audit_events,
                    counts=counts,
                    trace_id=trace_id,
                )
                return TenantPurgeResult(dry_run=True, status="DRY_RUN", counts=counts)

            locked_tenant = (
                self.db.execute(
                    select(Tenant).where(Tenant.id == tenant_id).with_for_update(nowait=True),
                )
                .scalar_one_or_none()
            )
            if locked_tenant is None:
                raise AppError(ErrorCatalog.TENANT_NOT_FOUND)

            if (locked_tenant.status or "").upper() != "SUSPENDED":
                locked_tenant.status = "SUSPENDED"
                self.db.flush()
                self.db.commit()

            deleted_counts = self._delete_in_order(tenant_id=tenant_id, preserve_audit_events=preserve_audit_events)
            self._audit_completed(
                tenant_id=tenant_id,
                actor=actor,
                reason=reason,
                dry_run=False,
                preserve_audit_events=preserve_audit_events,
                counts=deleted_counts,
                trace_id=trace_id,
            )
            return TenantPurgeResult(dry_run=False, status="COMPLETED", counts=deleted_counts)
        except Exception:
            self.db.rollback()
            self._audit_failed(
                tenant_id=tenant_id,
                actor=actor,
                reason=reason,
                dry_run=dry_run,
                preserve_audit_events=preserve_audit_events,
                trace_id=trace_id,
            )
            raise
        finally:
            self._release_lock(lock)

    def _acquire_lock(self, *, tenant_id: str, trace_id: str | None) -> TenantPurgeLock:
        lock = TenantPurgeLock(tenant_id=tenant_id, trace_id=trace_id)
        self.db.add(lock)
        try:
            self.db.commit()
            self.db.refresh(lock)
            return lock
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                ErrorCatalog.BUSINESS_CONFLICT,
                details={"message": "Tenant purge already in progress", "tenant_id": tenant_id},
            ) from exc
        except OperationalError as exc:
            self.db.rollback()
            raise AppError(ErrorCatalog.LOCK_TIMEOUT) from exc

    def _release_lock(self, lock: TenantPurgeLock) -> None:
        try:
            self.db.delete(lock)
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _counts(self, *, tenant_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for name, model in PURGE_ORDER[:-1]:
            counts[name] = int(
                self.db.execute(select(func.count()).select_from(model).where(model.tenant_id == tenant_id)).scalar_one()
                or 0
            )
        return counts

    def _delete_in_order(self, *, tenant_id: str, preserve_audit_events: bool) -> dict[str, int]:
        deleted_counts: dict[str, int] = {}

        for name, model in PURGE_ORDER[:-1]:
            result = self.db.execute(delete(model).where(model.tenant_id == tenant_id))
            deleted_counts[name] = int(result.rowcount or 0)

        # Additional tenant FK dependencies outside the requested list.
        role_template_ids = list(
            self.db.execute(select(RoleTemplate.id).where(RoleTemplate.tenant_id == tenant_id)).scalars().all()
        )
        if role_template_ids:
            self.db.execute(delete(RoleTemplatePermission).where(RoleTemplatePermission.role_template_id.in_(role_template_ids)))
            self.db.execute(delete(RoleTemplate).where(RoleTemplate.id.in_(role_template_ids)))
        self.db.execute(delete(VariantFieldSettings).where(VariantFieldSettings.tenant_id == tenant_id))
        self.db.execute(delete(ReturnPolicySettings).where(ReturnPolicySettings.tenant_id == tenant_id))

        if not preserve_audit_events:
            self.db.execute(
                delete(AuditEvent).where(
                    AuditEvent.tenant_id == tenant_id,
                    AuditEvent.action.notin_(
                        [
                            "admin.tenant.purge.started",
                            "admin.tenant.purge.completed",
                            "admin.tenant.purge.failed",
                        ]
                    ),
                )
            )

        tenant_result = self.db.execute(delete(Tenant).where(Tenant.id == tenant_id))
        deleted_counts["tenants"] = int(tenant_result.rowcount or 0)
        self.db.commit()
        return deleted_counts

    def _audit_started(self, *, tenant_id: str, actor, reason: str | None, dry_run: bool, preserve_audit_events: bool, trace_id: str | None) -> None:
        self.audit.record_event(
            AuditEventPayload(
                tenant_id=tenant_id,
                user_id=str(actor.id),
                store_id=str(actor.store_id) if actor.store_id else None,
                trace_id=trace_id,
                actor=actor.username,
                actor_role=actor.role,
                action="admin.tenant.purge.started",
                entity_type="tenant",
                entity_id=tenant_id,
                before=None,
                after=None,
                metadata={"reason": reason, "dry_run": dry_run, "preserve_audit_events": preserve_audit_events},
                result="success",
            )
        )

    def _audit_completed(self, *, tenant_id: str, actor, reason: str | None, dry_run: bool, preserve_audit_events: bool, counts: dict[str, int], trace_id: str | None) -> None:
        self.audit.record_event(
            AuditEventPayload(
                tenant_id=tenant_id,
                user_id=str(actor.id),
                store_id=str(actor.store_id) if actor.store_id else None,
                trace_id=trace_id,
                actor=actor.username,
                actor_role=actor.role,
                action="admin.tenant.purge.completed",
                entity_type="tenant",
                entity_id=tenant_id,
                before=None,
                after=None,
                metadata={
                    "reason": reason,
                    "dry_run": dry_run,
                    "preserve_audit_events": preserve_audit_events,
                    "counts": counts,
                },
                result="success",
            )
        )

    def _audit_failed(self, *, tenant_id: str, actor, reason: str | None, dry_run: bool, preserve_audit_events: bool, trace_id: str | None) -> None:
        self.audit.record_event(
            AuditEventPayload(
                tenant_id=tenant_id,
                user_id=str(actor.id),
                store_id=str(actor.store_id) if actor.store_id else None,
                trace_id=trace_id,
                actor=actor.username,
                actor_role=actor.role,
                action="admin.tenant.purge.failed",
                entity_type="tenant",
                entity_id=tenant_id,
                before=None,
                after=None,
                metadata={"reason": reason, "dry_run": dry_run, "preserve_audit_events": preserve_audit_events},
                result="failure",
            )
        )
