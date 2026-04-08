from __future__ import annotations

from dataclasses import dataclass
import logging
import traceback
import uuid

from sqlalchemy import delete, func, or_, select
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
    PurgeLock,
    ReturnPolicySettings,
    RoleTemplate,
    RoleTemplatePermission,
    StockItem,
    Store,
    StoreRolePolicy,
    Tenant,
    TenantRolePolicy,
    Transfer,
    TransferLine,
    TransferMovement,
    User,
    UserPermissionOverride,
    VariantFieldSettings,
)
from app.aris3.services.audit import AuditEventPayload, AuditService

logger = logging.getLogger(__name__)


TENANT_PURGE_ORDER = (
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


@dataclass
class PurgeResult:
    dry_run: bool
    status: str
    would_delete_counts: dict[str, int]
    deleted_counts: dict[str, int] | None


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
        result = self.execute_tenant(
            tenant_id=tenant_id,
            actor=actor,
            reason=reason,
            dry_run=dry_run,
            preserve_audit_events=preserve_audit_events,
            trace_id=trace_id,
        )
        counts = result.would_delete_counts if result.dry_run else (result.deleted_counts or {})
        return TenantPurgeResult(dry_run=result.dry_run, status=result.status, counts=counts)

    def execute_tenant(
        self,
        *,
        tenant_id: str,
        actor,
        reason: str | None,
        dry_run: bool,
        preserve_audit_events: bool,
        trace_id: str | None,
    ) -> PurgeResult:
        tenant = self.db.get(Tenant, tenant_id)
        if tenant is None:
            raise AppError(ErrorCatalog.TENANT_NOT_FOUND)
        return self._execute_resource(
            resource="tenant",
            resource_id=tenant_id,
            tenant_id=tenant_id,
            actor=actor,
            reason=reason,
            dry_run=dry_run,
            preserve_audit_events=preserve_audit_events,
            trace_id=trace_id,
            count_fn=lambda: self._tenant_counts(tenant_id=tenant_id),
            delete_fn=lambda: self._delete_tenant_in_order(tenant_id=tenant_id, preserve_audit_events=preserve_audit_events),
        )

    def execute_store(
        self,
        *,
        store_id: str,
        actor,
        reason: str | None,
        dry_run: bool,
        preserve_audit_events: bool,
        trace_id: str | None,
    ) -> PurgeResult:
        store = self.db.get(Store, store_id)
        if store is None:
            raise AppError(ErrorCatalog.STORE_NOT_FOUND)
        return self._execute_resource(
            resource="store",
            resource_id=store_id,
            tenant_id=str(store.tenant_id),
            actor=actor,
            reason=reason,
            dry_run=dry_run,
            preserve_audit_events=preserve_audit_events,
            trace_id=trace_id,
            count_fn=lambda: self._store_counts(store_id=store_id),
            delete_fn=lambda: self._delete_store_in_order(store_id=store_id, preserve_audit_events=preserve_audit_events),
        )

    def execute_user(
        self,
        *,
        user_id: str,
        actor,
        reason: str | None,
        dry_run: bool,
        preserve_audit_events: bool,
        trace_id: str | None,
    ) -> PurgeResult:
        user = self.db.get(User, user_id)
        if user is None:
            raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "User not found"})
        return self._execute_resource(
            resource="user",
            resource_id=user_id,
            tenant_id=str(user.tenant_id),
            actor=actor,
            reason=reason,
            dry_run=dry_run,
            preserve_audit_events=preserve_audit_events,
            trace_id=trace_id,
            count_fn=lambda: self._user_counts(user_id=user_id),
            delete_fn=lambda: self._delete_user_in_order(user_id=user_id, preserve_audit_events=preserve_audit_events),
        )

    def _execute_resource(
        self,
        *,
        resource: str,
        resource_id: str,
        tenant_id: str,
        actor,
        reason: str | None,
        dry_run: bool,
        preserve_audit_events: bool,
        trace_id: str | None,
        count_fn,
        delete_fn,
    ) -> PurgeResult:
        actor_snapshot = self._snapshot_actor(actor)
        execution_step = "count"
        would_delete_counts = count_fn()
        lock: PurgeLock | None = None
        if not dry_run:
            execution_step = "acquire_lock"
            lock = self._acquire_lock(resource=resource, resource_id=resource_id, trace_id=trace_id)
        try:
            execution_step = "audit_started"
            self._audit_event(
                action=f"admin.{resource}.purge.started",
                tenant_id=tenant_id,
                resource=resource,
                resource_id=resource_id,
                actor_snapshot=actor_snapshot,
                reason=reason,
                dry_run=dry_run,
                preserve_audit_events=preserve_audit_events,
                trace_id=trace_id,
                counts=would_delete_counts,
                result="success",
            )
            if dry_run:
                execution_step = "audit_completed_dry_run"
                self._audit_event(
                    action=f"admin.{resource}.purge.completed",
                    tenant_id=tenant_id,
                    resource=resource,
                    resource_id=resource_id,
                    actor_snapshot=actor_snapshot,
                    reason=reason,
                    dry_run=True,
                    preserve_audit_events=preserve_audit_events,
                    trace_id=trace_id,
                    counts=would_delete_counts,
                    result="success",
                )
                return PurgeResult(dry_run=True, status="DRY_RUN", would_delete_counts=would_delete_counts, deleted_counts=None)

            execution_step = "delete"
            deleted_counts = delete_fn()
            execution_step = "audit_completed"
            self._audit_event(
                action=f"admin.{resource}.purge.completed",
                tenant_id=tenant_id,
                resource=resource,
                resource_id=resource_id,
                actor_snapshot=actor_snapshot,
                reason=reason,
                dry_run=False,
                preserve_audit_events=preserve_audit_events,
                trace_id=trace_id,
                counts=deleted_counts,
                result="success",
            )
            return PurgeResult(dry_run=False, status="COMPLETED", would_delete_counts=would_delete_counts, deleted_counts=deleted_counts)
        except Exception as exc:
            self.db.rollback()
            failure_location = _exception_location(exc)
            logger.exception(
                "Purge execution failed",
                extra={
                    "resource": resource,
                    "resource_id": resource_id,
                    "tenant_id": tenant_id,
                    "dry_run": dry_run,
                    "preserve_audit_events": preserve_audit_events,
                    "trace_id": trace_id,
                    "execution_step": execution_step,
                    "exception_class": exc.__class__.__name__,
                    "exception_file": failure_location["file"],
                    "exception_function": failure_location["function"],
                    "exception_line": failure_location["line"],
                },
            )
            try:
                self._audit_event(
                    action=f"admin.{resource}.purge.failed",
                    tenant_id=tenant_id,
                    resource=resource,
                    resource_id=resource_id,
                    actor_snapshot=actor_snapshot,
                    reason=reason,
                    dry_run=dry_run,
                    preserve_audit_events=preserve_audit_events,
                    trace_id=trace_id,
                    counts=would_delete_counts,
                    result="failure",
                )
            except Exception:
                logger.exception(
                    "Failed to record purge failure audit event",
                    extra={
                        "resource": resource,
                        "resource_id": resource_id,
                        "tenant_id": tenant_id,
                        "trace_id": trace_id,
                        "execution_step": execution_step,
                    },
                )
            raise
        finally:
            if lock is not None:
                self._release_lock(lock)

    def _snapshot_actor(self, actor) -> dict[str, str | None]:
        return {
            "id": str(actor.id),
            "store_id": str(actor.store_id) if actor.store_id else None,
            "username": actor.username,
            "role": actor.role,
        }

    def _acquire_lock(self, *, resource: str, resource_id: str, trace_id: str | None) -> PurgeLock:
        lock = PurgeLock(resource_type=resource, resource_id=resource_id, trace_id=trace_id)
        self.db.add(lock)
        try:
            self.db.commit()
            self.db.refresh(lock)
            return lock
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(
                ErrorCatalog.BUSINESS_CONFLICT,
                details={"message": f"{resource.capitalize()} purge already in progress", "resource": resource, "resource_id": resource_id},
            ) from exc
        except OperationalError as exc:
            self.db.rollback()
            raise AppError(ErrorCatalog.LOCK_TIMEOUT) from exc

    def _release_lock(self, lock: PurgeLock) -> None:
        try:
            self.db.delete(lock)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()

    def _tenant_counts(self, *, tenant_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for name, model in TENANT_PURGE_ORDER[:-1]:
            counts[name] = int(
                self.db.execute(select(func.count()).select_from(model).where(model.tenant_id == tenant_id)).scalar_one() or 0
            )
        counts["tenants"] = 1
        return counts

    def _delete_tenant_in_order(self, *, tenant_id: str, preserve_audit_events: bool) -> dict[str, int]:
        deleted_counts: dict[str, int] = {}
        for name, model in TENANT_PURGE_ORDER[:-1]:
            result = self.db.execute(delete(model).where(model.tenant_id == tenant_id))
            deleted_counts[name] = int(result.rowcount or 0)

        role_template_ids = list(self.db.execute(select(RoleTemplate.id).where(RoleTemplate.tenant_id == tenant_id)).scalars().all())
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

    def _store_counts(self, *, store_id: str) -> dict[str, int]:
        transfer_filter = or_(Transfer.origin_store_id == store_id, Transfer.destination_store_id == store_id)
        transfer_ids_subq = select(Transfer.id).where(transfer_filter)
        sale_ids_subq = select(PosSale.id).where(PosSale.store_id == store_id)
        user_ids_subq = select(User.id).where(User.store_id == store_id)
        return {
            "transfer_movements": int(
                self.db.execute(select(func.count()).select_from(TransferMovement).where(TransferMovement.transfer_id.in_(transfer_ids_subq))).scalar_one() or 0
            ),
            "transfer_lines": int(
                self.db.execute(select(func.count()).select_from(TransferLine).where(TransferLine.transfer_id.in_(transfer_ids_subq))).scalar_one() or 0
            ),
            "sale_lines": int(self.db.execute(select(func.count()).select_from(PosSaleLine).where(PosSaleLine.sale_id.in_(sale_ids_subq))).scalar_one() or 0),
            "payments": int(self.db.execute(select(func.count()).select_from(PosPayment).where(PosPayment.sale_id.in_(sale_ids_subq))).scalar_one() or 0),
            "users": int(self.db.execute(select(func.count()).select_from(User).where(User.store_id == store_id)).scalar_one() or 0),
            "user_permission_overrides": int(
                self.db.execute(select(func.count()).select_from(UserPermissionOverride).where(UserPermissionOverride.user_id.in_(user_ids_subq))).scalar_one() or 0
            ),
            "transfers": int(self.db.execute(select(func.count()).select_from(Transfer).where(transfer_filter)).scalar_one() or 0),
            "sales": int(self.db.execute(select(func.count()).select_from(PosSale).where(PosSale.store_id == store_id)).scalar_one() or 0),
            "returns": int(self.db.execute(select(func.count()).select_from(PosReturnEvent).where(PosReturnEvent.store_id == store_id)).scalar_one() or 0),
            "cash_sessions": int(self.db.execute(select(func.count()).select_from(PosCashSession).where(PosCashSession.store_id == store_id)).scalar_one() or 0),
            "cash_movements": int(self.db.execute(select(func.count()).select_from(PosCashMovement).where(PosCashMovement.store_id == store_id)).scalar_one() or 0),
            "cash_day_closes": int(self.db.execute(select(func.count()).select_from(PosCashDayClose).where(PosCashDayClose.store_id == store_id)).scalar_one() or 0),
            "exports": int(self.db.execute(select(func.count()).select_from(ExportRecord).where(ExportRecord.store_id == store_id)).scalar_one() or 0),
            "store_role_policies": int(self.db.execute(select(func.count()).select_from(StoreRolePolicy).where(StoreRolePolicy.store_id == store_id)).scalar_one() or 0),
            "stock_items": int(self.db.execute(select(func.count()).select_from(StockItem).where(StockItem.store_id == store_id)).scalar_one() or 0),
            "stores": 1,
        }

    def _delete_store_in_order(self, *, store_id: str, preserve_audit_events: bool) -> dict[str, int]:
        deleted_counts = {k: 0 for k in self._store_counts(store_id=store_id).keys()}

        transfer_ids = list(
            self.db.execute(select(Transfer.id).where(or_(Transfer.origin_store_id == store_id, Transfer.destination_store_id == store_id))).scalars().all()
        )
        if transfer_ids:
            deleted_counts["transfer_movements"] = int(
                self.db.execute(delete(TransferMovement).where(TransferMovement.transfer_id.in_(transfer_ids))).rowcount or 0
            )
            deleted_counts["transfer_lines"] = int(self.db.execute(delete(TransferLine).where(TransferLine.transfer_id.in_(transfer_ids))).rowcount or 0)
            deleted_counts["transfers"] = int(self.db.execute(delete(Transfer).where(Transfer.id.in_(transfer_ids))).rowcount or 0)

        sale_ids = list(self.db.execute(select(PosSale.id).where(PosSale.store_id == store_id)).scalars().all())
        if sale_ids:
            deleted_counts["payments"] = int(self.db.execute(delete(PosPayment).where(PosPayment.sale_id.in_(sale_ids))).rowcount or 0)
            deleted_counts["sale_lines"] = int(self.db.execute(delete(PosSaleLine).where(PosSaleLine.sale_id.in_(sale_ids))).rowcount or 0)

        deleted_counts["returns"] = int(self.db.execute(delete(PosReturnEvent).where(PosReturnEvent.store_id == store_id)).rowcount or 0)
        deleted_counts["sales"] = int(self.db.execute(delete(PosSale).where(PosSale.store_id == store_id)).rowcount or 0)
        deleted_counts["cash_day_closes"] = int(self.db.execute(delete(PosCashDayClose).where(PosCashDayClose.store_id == store_id)).rowcount or 0)
        deleted_counts["cash_movements"] = int(self.db.execute(delete(PosCashMovement).where(PosCashMovement.store_id == store_id)).rowcount or 0)
        deleted_counts["cash_sessions"] = int(self.db.execute(delete(PosCashSession).where(PosCashSession.store_id == store_id)).rowcount or 0)
        deleted_counts["exports"] = int(self.db.execute(delete(ExportRecord).where(ExportRecord.store_id == store_id)).rowcount or 0)
        deleted_counts["store_role_policies"] = int(self.db.execute(delete(StoreRolePolicy).where(StoreRolePolicy.store_id == store_id)).rowcount or 0)
        deleted_counts["stock_items"] = int(self.db.execute(delete(StockItem).where(StockItem.store_id == store_id)).rowcount or 0)

        user_ids = list(self.db.execute(select(User.id).where(User.store_id == store_id)).scalars().all())
        if user_ids:
            self._nullify_transfer_actor_refs_for_users(user_ids=user_ids)
            deleted_counts["user_permission_overrides"] = int(
                self.db.execute(delete(UserPermissionOverride).where(UserPermissionOverride.user_id.in_(user_ids))).rowcount or 0
            )
            deleted_counts["users"] = int(self.db.execute(delete(User).where(User.id.in_(user_ids))).rowcount or 0)

        if not preserve_audit_events:
            self.db.execute(
                delete(AuditEvent).where(
                    AuditEvent.store_id == store_id,
                    AuditEvent.action.notin_([
                        "admin.store.purge.started",
                        "admin.store.purge.completed",
                        "admin.store.purge.failed",
                    ]),
                )
            )

        deleted_counts["stores"] = int(self.db.execute(delete(Store).where(Store.id == store_id)).rowcount or 0)
        self.db.commit()
        return deleted_counts

    def _user_counts(self, *, user_id: str) -> dict[str, int]:
        normalized_user_id = uuid.UUID(str(user_id))
        return {
            "user_permission_overrides": int(
                self.db.execute(select(func.count()).select_from(UserPermissionOverride).where(UserPermissionOverride.user_id == normalized_user_id)).scalar_one()
                or 0
            ),
            "transfers_as_creator": int(
                self.db.execute(select(func.count()).select_from(Transfer).where(Transfer.created_by_user_id == normalized_user_id)).scalar_one() or 0
            ),
            "transfers_as_editor": int(
                self.db.execute(select(func.count()).select_from(Transfer).where(Transfer.updated_by_user_id == normalized_user_id)).scalar_one() or 0
            ),
            "transfers_as_dispatcher": int(
                self.db.execute(select(func.count()).select_from(Transfer).where(Transfer.dispatched_by_user_id == normalized_user_id)).scalar_one() or 0
            ),
            "transfers_as_canceler": int(
                self.db.execute(select(func.count()).select_from(Transfer).where(Transfer.canceled_by_user_id == normalized_user_id)).scalar_one() or 0
            ),
            "users": 1,
        }

    def _delete_user_in_order(self, *, user_id: str, preserve_audit_events: bool) -> dict[str, int]:
        normalized_user_id = uuid.UUID(str(user_id))
        deleted_counts = {k: 0 for k in self._user_counts(user_id=user_id).keys()}
        actor_updates = self._nullify_transfer_actor_refs_for_users(user_ids=[str(normalized_user_id)])
        deleted_counts["transfers_as_creator"] = actor_updates["transfers_as_creator"]
        deleted_counts["transfers_as_editor"] = actor_updates["transfers_as_editor"]
        deleted_counts["transfers_as_dispatcher"] = actor_updates["transfers_as_dispatcher"]
        deleted_counts["transfers_as_canceler"] = actor_updates["transfers_as_canceler"]
        deleted_counts["user_permission_overrides"] = int(
            self.db.execute(delete(UserPermissionOverride).where(UserPermissionOverride.user_id == normalized_user_id)).rowcount or 0
        )

        if not preserve_audit_events:
            self.db.execute(
                delete(AuditEvent).where(
                    AuditEvent.user_id == normalized_user_id,
                    AuditEvent.action.notin_([
                        "admin.user.purge.started",
                        "admin.user.purge.completed",
                        "admin.user.purge.failed",
                    ]),
                )
            )

        deleted_counts["users"] = int(self.db.execute(delete(User).where(User.id == normalized_user_id)).rowcount or 0)
        self.db.commit()
        return deleted_counts

    def _nullify_transfer_actor_refs_for_users(self, *, user_ids: list[str]) -> dict[str, int]:
        if not user_ids:
            return {
                "transfers_as_creator": 0,
                "transfers_as_editor": 0,
                "transfers_as_dispatcher": 0,
                "transfers_as_canceler": 0,
            }
        normalized_user_ids = [uuid.UUID(str(user_id)) for user_id in user_ids]
        return {
            "transfers_as_creator": int(
                self.db.execute(
                    Transfer.__table__.update().where(Transfer.created_by_user_id.in_(normalized_user_ids)).values(created_by_user_id=None)
                ).rowcount
                or 0
            ),
            "transfers_as_editor": int(
                self.db.execute(
                    Transfer.__table__.update().where(Transfer.updated_by_user_id.in_(normalized_user_ids)).values(updated_by_user_id=None)
                ).rowcount
                or 0
            ),
            "transfers_as_dispatcher": int(
                self.db.execute(
                    Transfer.__table__.update()
                    .where(Transfer.dispatched_by_user_id.in_(normalized_user_ids))
                    .values(dispatched_by_user_id=None)
                ).rowcount
                or 0
            ),
            "transfers_as_canceler": int(
                self.db.execute(
                    Transfer.__table__.update().where(Transfer.canceled_by_user_id.in_(normalized_user_ids)).values(canceled_by_user_id=None)
                ).rowcount
                or 0
            ),
        }

    # Backward compatible hook for existing tests.
    def _delete_in_order(self, *, tenant_id: str, preserve_audit_events: bool) -> dict[str, int]:
        return self._delete_tenant_in_order(tenant_id=tenant_id, preserve_audit_events=preserve_audit_events)

    def _audit_event(
        self,
        *,
        action: str,
        tenant_id: str,
        resource: str,
        resource_id: str,
        actor_snapshot: dict[str, str | None],
        reason: str | None,
        dry_run: bool,
        preserve_audit_events: bool,
        trace_id: str | None,
        counts: dict[str, int],
        result: str,
    ) -> None:
        self.audit.record_event(
            AuditEventPayload(
                tenant_id=tenant_id,
                user_id=actor_snapshot["id"],
                store_id=actor_snapshot["store_id"],
                trace_id=trace_id,
                actor=actor_snapshot["username"] or "unknown",
                actor_role=actor_snapshot["role"],
                action=action,
                entity_type=resource,
                entity_id=resource_id,
                before=None,
                after=None,
                metadata={
                    "reason": reason,
                    "dry_run": dry_run,
                    "preserve_audit_events": preserve_audit_events,
                    "counts": counts,
                },
                result=result,
            )
        )


def _exception_location(exc: Exception) -> dict[str, str | int | None]:
    tb = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    if not tb:
        return {"file": None, "function": None, "line": None}
    last = tb[-1]
    return {"file": last.filename, "function": last.name, "line": last.lineno}
