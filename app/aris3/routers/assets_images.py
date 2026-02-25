from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from app.aris3.core.deps import get_current_token_data, require_active_user
from app.aris3.core.scope import can_write_stock_or_assets, is_superadmin
from app.aris3.db.models import Store
from app.aris3.db.session import get_db
from app.aris3.schemas.assets_images import ImageUploadResponse
from app.aris3.services.spaces_images import SpacesImageService, SpacesImageUploadError

router = APIRouter()
_ALLOWED_ROLES = {"SUPERADMIN", "ADMIN"}


def _resolve_tenant_scope(token_data, tenant_id: str | None) -> str:
    if is_superadmin(token_data.role):
        resolved_tenant_id = tenant_id or token_data.tenant_id
        if not resolved_tenant_id:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "TENANT_SCOPE_REQUIRED",
                    "message": "tenant_id is required",
                    "details": None,
                },
            )
        return resolved_tenant_id

    if not token_data.tenant_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "TENANT_SCOPE_REQUIRED",
                "message": "tenant_id is required",
                "details": None,
            },
        )

    if tenant_id and tenant_id != token_data.tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "CROSS_TENANT_ACCESS_DENIED",
                "message": "Cross tenant access denied",
                "details": {"tenant_id": tenant_id},
            },
        )

    return token_data.tenant_id


def _validate_store_scope(db, *, tenant_id: str, store_id: str) -> None:
    store_exists = db.execute(
        select(Store.id).where(Store.id == store_id, Store.tenant_id == tenant_id)
    ).scalar_one_or_none()
    if not store_exists:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "CROSS_TENANT_ACCESS_DENIED",
                "message": "store_id is outside tenant scope",
                "details": {"store_id": store_id, "tenant_id": tenant_id},
            },
        )


@router.post("/aris3/assets/upload-image", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    tenant_id: str | None = Form(default=None),
    store_id: str | None = Form(default=None),
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    if not can_write_stock_or_assets(token_data.role):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PERMISSION_DENIED",
                "message": "Solo ADMIN (tenant) o SUPERADMIN",
                "details": {"allowed_roles": sorted(_ALLOWED_ROLES)},
            },
        )

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BAD_REQUEST",
                "message": "file is required",
                "details": {"field": "file"},
            },
        )

    resolved_tenant_id = _resolve_tenant_scope(token_data, tenant_id)
    resolved_store_id = store_id or token_data.store_id
    if resolved_store_id:
        _validate_store_scope(db, tenant_id=resolved_tenant_id, store_id=resolved_store_id)

    file_bytes = await file.read()

    service = SpacesImageService()
    try:
        result = service.upload_image(
            file_bytes=file_bytes,
            original_filename=file.filename,
            content_type=file.content_type,
            tenant_id=resolved_tenant_id,
            store_id=resolved_store_id,
        )
    except SpacesImageUploadError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BAD_REQUEST",
                "message": str(exc),
                "details": None,
            },
        ) from exc

    return ImageUploadResponse(
        image_asset_id=result.image_asset_id,
        image_url=result.image_url,
        image_thumb_url=result.image_thumb_url,
        image_source=result.image_source,
        image_updated_at=result.image_updated_at,
    )
