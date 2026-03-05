from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, JSONResponse
import os

from app.aris3.core.config import settings
from app.aris3.core.deps import get_current_token_data, require_active_user, require_permission
from app.aris3.core.error_catalog import AppError, ErrorCatalog
from app.aris3.core.scope import DEFAULT_BROAD_STORE_ROLES, enforce_store_scope
from app.aris3.db.models import ExportRecord
from app.aris3.db.session import get_db
from app.aris3.repos.exports import ExportRepository
from app.aris3.schemas.exports import ExportCreateRequest, ExportFilters, ExportListResponse, ExportResponse
from app.aris3.services.audit import AuditEventPayload, AuditService
from app.aris3.services.exports import (
    ExportStorage,
    build_report_dataset,
    checksum_bytes,
    render_csv,
    render_pdf,
    render_xlsx,
    sanitize_filename,
)
from app.aris3.services.idempotency import IdempotencyService, extract_idempotency_key
from app.aris3.services.reports import resolve_date_range, resolve_timezone


router = APIRouter()
logger = logging.getLogger(__name__)


def _validation_error(field: str, message: str, error_type: str = "value_error") -> AppError:
    return AppError(
        ErrorCatalog.VALIDATION_ERROR,
        details={"errors": [{"field": field, "message": message, "type": error_type}]},
    )


def _normalize_filters_snapshot(filters: ExportFilters, *, store_id: str) -> ExportFilters:
    tz = resolve_timezone(filters.timezone)
    date_range = resolve_date_range(filters.from_value, filters.to_value, tz)
    return ExportFilters(
        store_id=store_id,
        **{
            "from": date_range.start_local.isoformat(),
            "to": date_range.end_local.isoformat(),
        },
        timezone=str(tz),
        cashier=filters.cashier,
        channel=filters.channel,
        payment_method=filters.payment_method,
    )


def _resolve_store_id(token_data, store_id: str | None) -> str:
    if store_id:
        return store_id
    if token_data.store_id:
        return token_data.store_id
    raise AppError(ErrorCatalog.STORE_SCOPE_REQUIRED)


def _store_scope_filter(token_data) -> str | None:
    if not token_data.store_id:
        return None
    role = (token_data.role or "").upper()
    if role in DEFAULT_BROAD_STORE_ROLES:
        return None
    return token_data.store_id


def _export_response(record: ExportRecord) -> ExportResponse:
    return ExportResponse(
        export_id=str(record.id),
        tenant_id=str(record.tenant_id),
        store_id=str(record.store_id),
        source_type=record.source_type,
        format=record.format,
        filters_snapshot=record.filters_snapshot,
        status=record.status,
        row_count=record.row_count,
        checksum_sha256=record.checksum_sha256,
        failure_reason_code=record.failure_reason_code,
        generated_by_user_id=str(record.generated_by_user_id) if record.generated_by_user_id else None,
        generated_at=record.generated_at,
        trace_id=record.trace_id,
        file_size_bytes=record.file_size_bytes,
        content_type=record.content_type,
        file_name=record.file_name,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _render_export_bytes(dataset, format: str, *, title: str, filters: dict, generated_at: datetime) -> tuple[bytes, str]:
    if format == "csv":
        return render_csv(dataset), "text/csv"
    if format == "xlsx":
        return (
            render_xlsx(dataset),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    if format == "pdf":
        return render_pdf(dataset, title=title, filters=filters, generated_at=generated_at), "application/pdf"
    raise _validation_error("format", "unsupported format")


@router.post(
    "/aris3/exports",
    response_model=ExportResponse,
    status_code=201,
    responses={
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
                }
            },
        }
    },
)
def create_export(
    request: Request,
    payload: ExportCreateRequest,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("REPORTS_VIEW")),
    db=Depends(get_db),
):
    if not payload.transaction_id:
        raise _validation_error("transaction_id", "transaction_id is required", "value_error.missing")
    idempotency_key = extract_idempotency_key(request.headers, required=True)
    request_hash = IdempotencyService.fingerprint(payload.model_dump(mode="json"))
    idempotency_service = IdempotencyService(db)
    context, replay = idempotency_service.start(
        tenant_id=token_data.tenant_id,
        endpoint=str(request.url.path),
        method=request.method,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if replay:
        return JSONResponse(
            status_code=replay.status_code,
            content=replay.response_body,
            headers={"X-Idempotency-Result": ErrorCatalog.IDEMPOTENCY_REPLAY.code},
        )
    request.state.idempotency = context

    resolved_store_id = _resolve_store_id(token_data, payload.filters.store_id)
    store = enforce_store_scope(
        token_data,
        resolved_store_id,
        db,
        allow_superadmin=True,
        broader_store_roles=DEFAULT_BROAD_STORE_ROLES,
    )
    storage = ExportStorage(settings.EXPORTS_STORAGE_PATH)
    repo = ExportRepository(db)
    normalized_filters = _normalize_filters_snapshot(payload.filters, store_id=resolved_store_id)
    filters_snapshot = normalized_filters.snapshot()
    export_record = ExportRecord(
        tenant_id=store.tenant_id,
        store_id=store.id,
        source_type=payload.source_type,
        format=payload.format,
        filters_snapshot=filters_snapshot,
        status="CREATED",
        row_count=0,
        checksum_sha256=None,
        failure_reason_code=None,
        file_size_bytes=None,
        content_type=None,
        file_name=None,
        file_path=None,
        generated_by_user_id=current_user.id,
        generated_at=None,
        trace_id=getattr(request.state, "trace_id", None),
    )
    export_record = repo.create(export_record)
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=str(store.tenant_id),
            user_id=str(current_user.id),
            store_id=str(store.id),
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="exports.create",
            entity_type="export",
            entity_id=str(export_record.id),
            before=None,
            after=_export_response(export_record).model_dump(mode="json"),
            metadata={"transaction_id": payload.transaction_id},
            result="success",
        )
    )

    start_time = datetime.utcnow()
    try:
        dataset = build_report_dataset(
            db=db,
            tenant_id=str(store.tenant_id),
            store_id=resolved_store_id,
            source_type=payload.source_type,
            filters=payload.filters,
            max_days=settings.REPORTS_MAX_DATE_RANGE_DAYS,
        )
        if settings.EXPORTS_MAX_ROWS > 0 and len(dataset.rows) > settings.EXPORTS_MAX_ROWS:
            raise AppError(
                ErrorCatalog.VALIDATION_ERROR,
                details={
                    "errors": [{"field": "filters", "message": "export rows exceed limit", "type": "value_error.rows_limit"}],
                    "reason_code": "EXPORT_ROWS_LIMIT_EXCEEDED",
                    "max_rows": settings.EXPORTS_MAX_ROWS,
                },
            )
        generated_at = datetime.utcnow()
        file_bytes, content_type = _render_export_bytes(
            dataset,
            payload.format,
            title=f"ARIS Report Export - {payload.source_type}",
            filters=normalized_filters.snapshot(),
            generated_at=generated_at,
        )
        checksum = checksum_bytes(file_bytes)
        file_path = storage.build_path(str(export_record.id), payload.format)
        storage.write_bytes(file_path, file_bytes)
        export_record.status = "READY"
        export_record.row_count = len(dataset.rows)
        export_record.checksum_sha256 = checksum
        export_record.file_size_bytes = len(file_bytes)
        export_record.content_type = content_type
        export_record.file_name = sanitize_filename(
            payload.file_name,
            payload.format,
            fallback=f"export-{export_record.id}",
        )
        export_record.file_path = file_path
        export_record.generated_at = generated_at
        export_record.updated_at = datetime.utcnow()
        export_record = repo.update(export_record)
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=str(store.tenant_id),
                user_id=str(current_user.id),
                store_id=str(store.id),
                trace_id=getattr(request.state, "trace_id", "") or None,
                actor=current_user.username,
                action="exports.finalize",
                entity_type="export",
                entity_id=str(export_record.id),
                before=None,
                after=_export_response(export_record).model_dump(mode="json"),
                metadata={"status": "READY"},
                result="success",
            )
        )
        logger.info(
            "exports_create",
            extra={
                "trace_id": export_record.trace_id,
                "tenant_id": str(store.tenant_id),
                "store_id": resolved_store_id,
                "endpoint": "/aris3/exports",
                "latency_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
                "row_count": export_record.row_count,
                "export_id": str(export_record.id),
            },
        )
    except AppError as exc:
        reason_code = None
        if isinstance(exc.details, dict):
            reason_code = exc.details.get("reason_code")
        export_record.status = "FAILED"
        export_record.failure_reason_code = reason_code or "EXPORT_FAILED"
        export_record.updated_at = datetime.utcnow()
        repo.update(export_record)
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=str(store.tenant_id),
                user_id=str(current_user.id),
                store_id=str(store.id),
                trace_id=getattr(request.state, "trace_id", "") or None,
                actor=current_user.username,
                action="exports.finalize",
                entity_type="export",
                entity_id=str(export_record.id),
                before=None,
                after=_export_response(export_record).model_dump(mode="json"),
                metadata={"status": "FAILED", "reason_code": export_record.failure_reason_code},
                result="failure",
            )
        )
        logger.info(
            "exports_failed",
            extra={
                "trace_id": export_record.trace_id,
                "tenant_id": str(store.tenant_id),
                "store_id": resolved_store_id,
                "endpoint": "/aris3/exports",
                "latency_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
                "row_count": export_record.row_count,
                "export_id": str(export_record.id),
                "reason_code": export_record.failure_reason_code,
            },
        )
        raise
    except Exception as exc:
        export_record.status = "FAILED"
        export_record.failure_reason_code = "EXPORT_FAILED"
        export_record.updated_at = datetime.utcnow()
        repo.update(export_record)
        AuditService(db).record_event(
            AuditEventPayload(
                tenant_id=str(store.tenant_id),
                user_id=str(current_user.id),
                store_id=str(store.id),
                trace_id=getattr(request.state, "trace_id", "") or None,
                actor=current_user.username,
                action="exports.finalize",
                entity_type="export",
                entity_id=str(export_record.id),
                before=None,
                after=_export_response(export_record).model_dump(mode="json"),
                metadata={"status": "FAILED", "reason_code": export_record.failure_reason_code},
                result="failure",
            )
        )
        logger.exception(
            "exports_failed",
            extra={
                "trace_id": export_record.trace_id,
                "tenant_id": str(store.tenant_id),
                "store_id": resolved_store_id,
                "endpoint": "/aris3/exports",
                "latency_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
                "row_count": export_record.row_count,
                "export_id": str(export_record.id),
                "reason_code": export_record.failure_reason_code,
            },
        )
        raise AppError(ErrorCatalog.INTERNAL_ERROR, details={"message": "export generation failed"}) from exc

    response = _export_response(export_record)
    context.record_success(status_code=201, response_body=response.model_dump(mode="json"))
    return response


@router.get(
    "/aris3/exports",
    response_model=ExportListResponse,
    responses={
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
                }
            },
        }
    },
)
def list_exports(
    token_data=Depends(get_current_token_data),
    _permission=Depends(require_permission("REPORTS_VIEW")),
    page_size: int | None = Query(None, ge=1, description="Optional page size. Defaults to EXPORTS_LIST_MAX_PAGE_SIZE and results are ordered by created_at desc."),
    db=Depends(get_db),
):
    repo = ExportRepository(db)
    store_filter = _store_scope_filter(token_data)
    if page_size is not None and page_size > settings.EXPORTS_LIST_MAX_PAGE_SIZE:
        raise AppError(
            ErrorCatalog.VALIDATION_ERROR,
            details={
                "errors": [
                    {
                        "field": "page_size",
                        "message": "page_size exceeds limit",
                        "type": "value_error.page_size_limit",
                    }
                ],
                "reason_code": "EXPORTS_PAGE_SIZE_LIMIT_EXCEEDED",
                "max_page_size": settings.EXPORTS_LIST_MAX_PAGE_SIZE,
            },
        )
    limit = page_size or settings.EXPORTS_LIST_MAX_PAGE_SIZE
    rows = repo.list_by_tenant(token_data.tenant_id, store_id=store_filter, limit=limit)
    return ExportListResponse(rows=[_export_response(record) for record in rows])


@router.get(
    "/aris3/exports/{export_id}",
    response_model=ExportResponse,
    responses={
        404: {
            "description": "Export not found",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/NotFoundErrorResponse"}
                }
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
                }
            },
        },
    },
)
def get_export(
    export_id: UUID,
    token_data=Depends(get_current_token_data),
    _permission=Depends(require_permission("REPORTS_VIEW")),
    db=Depends(get_db),
):
    repo = ExportRepository(db)
    export_id_str = str(export_id)
    record = repo.get_by_id(export_id_str, token_data.tenant_id)
    if not record:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "export not found", "export_id": export_id_str})
    enforce_store_scope(
        token_data,
        str(record.store_id),
        db,
        allow_superadmin=True,
        broader_store_roles=DEFAULT_BROAD_STORE_ROLES,
    )
    return _export_response(record)


@router.get(
    "/aris3/exports/{export_id}/download",
    response_class=FileResponse,
    responses={
        200: {
            "description": "Binary export file",
            "headers": {
                "Content-Type": {
                    "description": "MIME type of the generated export file.",
                    "schema": {"type": "string"},
                },
                "Content-Disposition": {
                    "description": "Attachment filename suggested by the server.",
                    "schema": {"type": "string"},
                },
                "Content-Length": {
                    "description": "Export file size in bytes.",
                    "schema": {"type": "integer"},
                },
            },
            "content": {
                "text/csv": {"schema": {"type": "string", "format": "binary"}},
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {"schema": {"type": "string", "format": "binary"}},
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}},
            },
        },
        404: {
            "description": "Export record or file not found",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/NotFoundErrorResponse"},
                    "examples": {
                        "export_not_found": {
                            "value": {
                                "code": "RESOURCE_NOT_FOUND",
                                "message": "Resource not found",
                                "details": {"message": "export not found", "export_id": "0f6f5b43-6c51-4e1f-a414-20c463db7001"},
                                "trace_id": "trace-exports-download-404-record",
                            }
                        },
                        "file_missing": {
                            "value": {
                                "code": "RESOURCE_NOT_FOUND",
                                "message": "Resource not found",
                                "details": {"message": "export file missing", "export_id": "0f6f5b43-6c51-4e1f-a414-20c463db7001"},
                                "trace_id": "trace-exports-download-404-file",
                            }
                        },
                    },
                }
            },
        },
        409: {
            "description": "Export exists but is not ready",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ConflictErrorResponse"},
                    "example": {
                        "code": "BUSINESS_CONFLICT",
                        "message": "Business conflict",
                        "details": {
                            "message": "export is still processing and not ready for download",
                            "export_id": "0f6f5b43-6c51-4e1f-a414-20c463db7001",
                            "status": "CREATED",
                        },
                        "trace_id": "trace-exports-download-409",
                    },
                }
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"},
                    "example": {
                        "code": "VALIDATION_ERROR",
                        "message": "Validation error",
                        "details": {
                            "errors": [
                                {"field": "export_id", "message": "Input should be a valid UUID", "type": "uuid_parsing"}
                            ]
                        },
                        "trace_id": "trace-exports-download-422",
                    },
                }
            },
        },
    },
)
def download_export(
    export_id: UUID,
    request: Request,
    token_data=Depends(get_current_token_data),
    current_user=Depends(require_active_user),
    _permission=Depends(require_permission("REPORTS_VIEW")),
    db=Depends(get_db),
):
    repo = ExportRepository(db)
    export_id_str = str(export_id)
    record = repo.get_by_id(export_id_str, token_data.tenant_id)
    if not record:
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "export not found", "export_id": export_id_str})
    enforce_store_scope(
        token_data,
        str(record.store_id),
        db,
        allow_superadmin=True,
        broader_store_roles=DEFAULT_BROAD_STORE_ROLES,
    )
    if record.status != "READY" or not record.file_path or not record.content_type:
        raise AppError(ErrorCatalog.BUSINESS_CONFLICT, details={"message": "export is still processing and not ready for download", "export_id": export_id_str, "status": record.status})
    if not os.path.exists(record.file_path):
        raise AppError(ErrorCatalog.RESOURCE_NOT_FOUND, details={"message": "export file missing", "export_id": export_id_str})
    response = FileResponse(
        path=record.file_path,
        media_type=record.content_type,
        filename=record.file_name or f"export-{record.id}.{record.format}",
    )
    logger.info(
        "exports_download",
        extra={
            "trace_id": getattr(request.state, "trace_id", None),
            "tenant_id": str(record.tenant_id),
            "store_id": str(record.store_id),
            "endpoint": "/aris3/exports/{export_id}/download",
            "latency_ms": None,
            "row_count": record.row_count,
            "export_id": str(record.id),
        },
    )
    AuditService(db).record_event(
        AuditEventPayload(
            tenant_id=str(record.tenant_id),
            user_id=str(current_user.id),
            store_id=str(record.store_id),
            trace_id=getattr(request.state, "trace_id", "") or None,
            actor=current_user.username,
            action="exports.download",
            entity_type="export",
            entity_id=str(record.id),
            before=None,
            after=None,
            metadata=None,
            result="success",
        )
    )
    return response
