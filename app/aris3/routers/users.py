from fastapi import APIRouter, Depends

from app.aris3.core.deps import get_current_token_data, require_request_context
from app.aris3.schemas.auth import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def me(token_data=Depends(get_current_token_data), context=Depends(require_request_context)):
    return UserResponse(
        id=context.user_id or token_data.sub,
        username=token_data.username,
        email=token_data.email,
        tenant_id=context.tenant_id or token_data.tenant_id,
        store_id=context.store_id or token_data.store_id,
        role=context.role or token_data.role,
        status=token_data.status,
        is_active=token_data.is_active,
        must_change_password=token_data.must_change_password,
    )
