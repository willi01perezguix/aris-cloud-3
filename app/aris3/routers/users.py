from fastapi import APIRouter, Depends

from app.aris3.core.security import get_current_user
from app.aris3.schemas.auth import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        tenant_id=str(current_user.tenant_id),
        role=current_user.role,
        must_change_password=current_user.must_change_password,
    )
