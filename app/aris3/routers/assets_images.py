from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.aris3.core.deps import get_current_token_data, require_active_user
from app.aris3.schemas.assets_images import ImageUploadResponse
from app.aris3.services.spaces_images import SpacesImageService, SpacesImageUploadError

router = APIRouter()

_ALLOWED_ROLES = {"SUPERADMIN", "PLATFORM_ADMIN", "TENANT_ADMIN"}


@router.post("/aris3/assets/upload-image", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    tenant_id: str | None = Form(default=None),
    store_id: str | None = Form(default=None),
    token_data=Depends(get_current_token_data),
    _current_user=Depends(require_active_user),
):
    role = (token_data.role or "").upper()
    if role not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PERMISSION_DENIED",
                "message": "Permission denied",
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

    resolved_tenant_id = tenant_id or token_data.tenant_id
    resolved_store_id = store_id or token_data.store_id
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
