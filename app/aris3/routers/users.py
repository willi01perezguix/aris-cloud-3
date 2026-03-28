from fastapi import APIRouter, Depends

from app.aris3.core.deps import require_active_user, require_request_context
from app.aris3.schemas.auth import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def me(
    context=Depends(require_request_context),
    current_user=Depends(require_active_user),
):
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        tenant_id=str(current_user.tenant_id),
        store_id=str(current_user.store_id) if current_user.store_id else None,
        role=current_user.role,
        status=current_user.status,
        is_active=current_user.is_active,
        must_change_password=current_user.must_change_password,
        trace_id=context.trace_id,
    )
