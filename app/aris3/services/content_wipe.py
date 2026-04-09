from __future__ import annotations

from dataclasses import dataclass
import logging

from sqlalchemy import delete, func, or_, select

from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.db.models import (
    AuditEvent,
    EpcAssignment,
    ExportRecord,
    IdempotencyRecord,
    PosCashDayClose,
    PosCashMovement,
    PosCashSession,
    PosPayment,
    PosReturnEvent,
    PosSale,
    PosSaleLine,
    PreloadLine,
    PreloadSession,
    PurgeLock,
    SkuImage,
    StockItem,
    Store,
    Tenant,
    Transfer,
    TransferLine,
    TransferMovement,
)
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.spaces_images import SpacesImageService, SpacesImageUploadError
from app.aris3.services.tenant_purge import _is_missing_purge_lock_table

logger = logging.getLogger(__name__)


@dataclass
class ContentWipeResult:
    dry_run: bool
    status: str
    would_delete_counts: dict[str, int]
    deleted_counts: dict[str, int] | None
    deleted_spaces_objects: int
    warnings: list[str]


class ContentWipeService:
    def __init__(self, db):
        self.db = db
        self.audit = AuditService(db)

    def execute_store_wipe(
        self,
        *,
        store_id: str,
        actor,
        reason: str | None,
        dry_run: bool,
        preserve_audit_events: bool,
        delete_store_audit_events: bool,
        delete_spaces_objects: bool,
        trace_id: str | None,
    ) -> ContentWipeResult:
        store = self.db.get(Store, store_id)
        if store is None:
            raise AppError(ErrorCatalog.STORE_NOT_FOUND)

        tenant_id = str(store.tenant_id)
        counts = self._store_counts(store_id=store_id)
        if delete_store_audit_events and not preserve_audit_events:
            counts["store_audit_events"] = self._count(select(func.count()).select_from(AuditEvent).where(AuditEvent.store_id == store_id))

        if dry_run:
            self._audit_event(
                action="admin.store.wipe_content.completed",
                tenant_id=tenant_id,
                resource="store",
                resource_id=store_id,
                actor=actor,
                reason=reason,
                dry_run=True,
                preserve_audit_events=preserve_audit_events,
                counts=counts,
                trace_id=trace_id,
                warnings=[],
            )
            return ContentWipeResult(
                dry_run=True,
                status="DRY_RUN",
                would_delete_counts=counts,
                deleted_counts=None,
                deleted_spaces_objects=0,
                warnings=[],
            )

        lock = self._acquire_lock(resource="store_content", resource_id=store_id, trace_id=trace_id)
        warnings: list[str] = []
        deleted_spaces_objects = 0
        try:
            deleted_counts = self._delete_store_content(store_id=store_id)
            if delete_store_audit_events and not preserve_audit_events:
                deleted_counts["store_audit_events"] = int(
                    self.db.execute(delete(AuditEvent).where(AuditEvent.store_id == store_id)).rowcount or 0
                )
            else:
                deleted_counts["store_audit_events"] = 0

            if delete_spaces_objects:
                spaces_result = self._delete_spaces_prefix(prefix=f"aris3/images/{tenant_id}/{store_id}/", trace_id=trace_id)
                deleted_spaces_objects = spaces_result.deleted_objects
                warnings.extend(spaces_result.warnings)

            self.db.commit()
            self._audit_event(
                action="admin.store.wipe_content.completed",
                tenant_id=tenant_id,
                resource="store",
                resource_id=store_id,
                actor=actor,
                reason=reason,
                dry_run=False,
                preserve_audit_events=preserve_audit_events,
                counts=deleted_counts,
                trace_id=trace_id,
                warnings=warnings,
            )
            return ContentWipeResult(
                dry_run=False,
                status="COMPLETED",
                would_delete_counts=counts,
                deleted_counts=deleted_counts,
                deleted_spaces_objects=deleted_spaces_objects,
                warnings=warnings,
            )
        except Exception:
            self.db.rollback()
            raise
        finally:
            if lock is not None:
                self._release_lock(lock)

    def execute_tenant_wipe(
        self,
        *,
        tenant_id: str,
        actor,
        reason: str | None,
        dry_run: bool,
        preserve_audit_events: bool,
        delete_tenant_audit_events: bool,
        delete_tenant_idempotency_records: bool,
        delete_spaces_objects: bool,
        trace_id: str | None,
    ) -> ContentWipeResult:
        tenant = self.db.get(Tenant, tenant_id)
        if tenant is None:
            raise AppError(ErrorCatalog.TENANT_NOT_FOUND)

        counts = self._tenant_counts(tenant_id=tenant_id)
        counts["tenant_audit_events"] = self._count(select(func.count()).select_from(AuditEvent).where(AuditEvent.tenant_id == tenant_id)) if delete_tenant_audit_events and not preserve_audit_events else 0
        counts["tenant_idempotency_records"] = self._count(select(func.count()).select_from(IdempotencyRecord).where(IdempotencyRecord.tenant_id == tenant_id)) if delete_tenant_idempotency_records else 0

        if dry_run:
            self._audit_event(
                action="admin.tenant.wipe_content.completed",
                tenant_id=tenant_id,
                resource="tenant",
                resource_id=tenant_id,
                actor=actor,
                reason=reason,
                dry_run=True,
                preserve_audit_events=preserve_audit_events,
                counts=counts,
                trace_id=trace_id,
                warnings=[],
            )
            return ContentWipeResult(True, "DRY_RUN", counts, None, 0, [])

        lock = self._acquire_lock(resource="tenant_content", resource_id=tenant_id, trace_id=trace_id)
        warnings: list[str] = []
        deleted_spaces_objects = 0
        try:
            deleted_counts = self._delete_tenant_content(tenant_id=tenant_id)
            deleted_counts["tenant_audit_events"] = int(
                self.db.execute(delete(AuditEvent).where(AuditEvent.tenant_id == tenant_id)).rowcount or 0
            ) if delete_tenant_audit_events and not preserve_audit_events else 0
            deleted_counts["tenant_idempotency_records"] = int(
                self.db.execute(delete(IdempotencyRecord).where(IdempotencyRecord.tenant_id == tenant_id)).rowcount or 0
            ) if delete_tenant_idempotency_records else 0

            if delete_spaces_objects:
                spaces_result = self._delete_spaces_prefix(prefix=f"aris3/images/{tenant_id}/", trace_id=trace_id)
                deleted_spaces_objects = spaces_result.deleted_objects
                warnings.extend(spaces_result.warnings)

            self.db.commit()
            self._audit_event(
                action="admin.tenant.wipe_content.completed",
                tenant_id=tenant_id,
                resource="tenant",
                resource_id=tenant_id,
                actor=actor,
                reason=reason,
                dry_run=False,
                preserve_audit_events=preserve_audit_events,
                counts=deleted_counts,
                trace_id=trace_id,
                warnings=warnings,
            )
            return ContentWipeResult(False, "COMPLETED", counts, deleted_counts, deleted_spaces_objects, warnings)
        except Exception:
            self.db.rollback()
            raise
        finally:
            if lock is not None:
                self._release_lock(lock)

    def _delete_store_content(self, *, store_id: str) -> dict[str, int]:
        deleted_counts = {k: 0 for k in self._store_counts(store_id=store_id).keys()}

        transfer_ids = list(
            self.db.execute(select(Transfer.id).where(or_(Transfer.origin_store_id == store_id, Transfer.destination_store_id == store_id))).scalars().all()
        )
        if transfer_ids:
            deleted_counts["transfer_movements"] = int(self.db.execute(delete(TransferMovement).where(TransferMovement.transfer_id.in_(transfer_ids))).rowcount or 0)
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
        deleted_counts["preload_lines"] = int(self.db.execute(delete(PreloadLine).where(PreloadLine.store_id == store_id)).rowcount or 0)
        deleted_counts["preload_sessions"] = int(self.db.execute(delete(PreloadSession).where(PreloadSession.store_id == store_id)).rowcount or 0)
        deleted_counts["epc_assignments"] = int(self.db.execute(delete(EpcAssignment).where(EpcAssignment.store_id == store_id)).rowcount or 0)
        deleted_counts["stock_items"] = int(self.db.execute(delete(StockItem).where(StockItem.store_id == store_id)).rowcount or 0)
        return deleted_counts

    def _delete_tenant_content(self, *, tenant_id: str) -> dict[str, int]:
        deleted_counts = {k: 0 for k in self._tenant_counts(tenant_id=tenant_id).keys()}
        for name, model in (
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
            ("sku_images", SkuImage),
            ("preload_lines", PreloadLine),
            ("preload_sessions", PreloadSession),
            ("epc_assignments", EpcAssignment),
            ("stock_items", StockItem),
        ):
            deleted_counts[name] = int(self.db.execute(delete(model).where(model.tenant_id == tenant_id)).rowcount or 0)
        return deleted_counts

    def _store_counts(self, *, store_id: str) -> dict[str, int]:
        transfer_filter = or_(Transfer.origin_store_id == store_id, Transfer.destination_store_id == store_id)
        transfer_ids_subq = select(Transfer.id).where(transfer_filter)
        sale_ids_subq = select(PosSale.id).where(PosSale.store_id == store_id)
        return {
            "transfer_movements": self._count(select(func.count()).select_from(TransferMovement).where(TransferMovement.transfer_id.in_(transfer_ids_subq))),
            "transfer_lines": self._count(select(func.count()).select_from(TransferLine).where(TransferLine.transfer_id.in_(transfer_ids_subq))),
            "transfers": self._count(select(func.count()).select_from(Transfer).where(transfer_filter)),
            "sale_lines": self._count(select(func.count()).select_from(PosSaleLine).where(PosSaleLine.sale_id.in_(sale_ids_subq))),
            "payments": self._count(select(func.count()).select_from(PosPayment).where(PosPayment.sale_id.in_(sale_ids_subq))),
            "returns": self._count(select(func.count()).select_from(PosReturnEvent).where(PosReturnEvent.store_id == store_id)),
            "sales": self._count(select(func.count()).select_from(PosSale).where(PosSale.store_id == store_id)),
            "cash_movements": self._count(select(func.count()).select_from(PosCashMovement).where(PosCashMovement.store_id == store_id)),
            "cash_sessions": self._count(select(func.count()).select_from(PosCashSession).where(PosCashSession.store_id == store_id)),
            "cash_day_closes": self._count(select(func.count()).select_from(PosCashDayClose).where(PosCashDayClose.store_id == store_id)),
            "exports": self._count(select(func.count()).select_from(ExportRecord).where(ExportRecord.store_id == store_id)),
            "preload_lines": self._count(select(func.count()).select_from(PreloadLine).where(PreloadLine.store_id == store_id)),
            "preload_sessions": self._count(select(func.count()).select_from(PreloadSession).where(PreloadSession.store_id == store_id)),
            "epc_assignments": self._count(select(func.count()).select_from(EpcAssignment).where(EpcAssignment.store_id == store_id)),
            "stock_items": self._count(select(func.count()).select_from(StockItem).where(StockItem.store_id == store_id)),
        }

    def _tenant_counts(self, *, tenant_id: str) -> dict[str, int]:
        return {
            "transfer_movements": self._count(select(func.count()).select_from(TransferMovement).where(TransferMovement.tenant_id == tenant_id)),
            "transfer_lines": self._count(select(func.count()).select_from(TransferLine).where(TransferLine.tenant_id == tenant_id)),
            "transfers": self._count(select(func.count()).select_from(Transfer).where(Transfer.tenant_id == tenant_id)),
            "sale_lines": self._count(select(func.count()).select_from(PosSaleLine).where(PosSaleLine.tenant_id == tenant_id)),
            "payments": self._count(select(func.count()).select_from(PosPayment).where(PosPayment.tenant_id == tenant_id)),
            "returns": self._count(select(func.count()).select_from(PosReturnEvent).where(PosReturnEvent.tenant_id == tenant_id)),
            "sales": self._count(select(func.count()).select_from(PosSale).where(PosSale.tenant_id == tenant_id)),
            "cash_movements": self._count(select(func.count()).select_from(PosCashMovement).where(PosCashMovement.tenant_id == tenant_id)),
            "cash_sessions": self._count(select(func.count()).select_from(PosCashSession).where(PosCashSession.tenant_id == tenant_id)),
            "cash_day_closes": self._count(select(func.count()).select_from(PosCashDayClose).where(PosCashDayClose.tenant_id == tenant_id)),
            "exports": self._count(select(func.count()).select_from(ExportRecord).where(ExportRecord.tenant_id == tenant_id)),
            "sku_images": self._count(select(func.count()).select_from(SkuImage).where(SkuImage.tenant_id == tenant_id)),
            "preload_lines": self._count(select(func.count()).select_from(PreloadLine).where(PreloadLine.tenant_id == tenant_id)),
            "preload_sessions": self._count(select(func.count()).select_from(PreloadSession).where(PreloadSession.tenant_id == tenant_id)),
            "epc_assignments": self._count(select(func.count()).select_from(EpcAssignment).where(EpcAssignment.tenant_id == tenant_id)),
            "stock_items": self._count(select(func.count()).select_from(StockItem).where(StockItem.tenant_id == tenant_id)),
        }

    def _count(self, stmt) -> int:
        return int(self.db.execute(stmt).scalar_one() or 0)

    def _acquire_lock(self, *, resource: str, resource_id: str, trace_id: str | None):
        lock = PurgeLock(resource_type=resource, resource_id=resource_id, trace_id=trace_id)
        self.db.add(lock)
        try:
            self.db.commit()
            self.db.refresh(lock)
            return lock
        except Exception as exc:
            self.db.rollback()
            if exc.__class__.__name__ == "IntegrityError":
                raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": f"{resource} wipe already in progress"}) from exc
            if exc.__class__.__name__ == "ProgrammingError" and _is_missing_purge_lock_table(exc):
                logger.warning("purge_locks table missing; continuing wipe without DB lock", extra={"resource": resource, "resource_id": resource_id})
                return None
            raise

    def _release_lock(self, lock: PurgeLock) -> None:
        try:
            self.db.delete(lock)
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _delete_spaces_prefix(self, *, prefix: str, trace_id: str | None):
        try:
            return SpacesImageService().delete_prefix_objects(prefix=prefix, trace_id=trace_id)
        except SpacesImageUploadError as exc:
            return type("_Result", (), {"deleted_objects": 0, "warnings": [str(exc)]})()
        except Exception as exc:
            logger.exception("spaces_delete_prefix_unhandled_error", extra={"prefix": prefix, "trace_id": trace_id})
            return type("_Result", (), {"deleted_objects": 0, "warnings": [f"unexpected spaces deletion error: {exc}"]})()

    def _audit_event(
        self,
        *,
        action: str,
        tenant_id: str,
        resource: str,
        resource_id: str,
        actor,
        reason: str | None,
        dry_run: bool,
        preserve_audit_events: bool,
        counts: dict[str, int],
        trace_id: str | None,
        warnings: list[str],
    ) -> None:
        self.audit.record_event(
            AuditEventPayload(
                tenant_id=tenant_id,
                user_id=str(actor.id) if actor else None,
                store_id=str(actor.store_id) if actor and actor.store_id else None,
                trace_id=trace_id,
                actor=actor.username if actor else "unknown",
                actor_role=actor.role if actor else None,
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
                    "warnings": warnings,
                },
                result="success",
            )
        )
