from fastapi import APIRouter, Depends

from app.aris3.core.security import get_current_token_data
from app.aris3.schemas.auth import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def me(token_data=Depends(get_current_token_data)):
    return UserResponse(
        id=token_data.sub,
        username=token_data.username,
        email=token_data.email,
        tenant_id=token_data.tenant_id,
        store_id=token_data.store_id,
        role=token_data.role,
        status=token_data.status,
        is_active=token_data.is_active,
        must_change_password=token_data.must_change_password,
    )
