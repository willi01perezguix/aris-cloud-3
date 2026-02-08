from fastapi import APIRouter, Depends

from app.aris3.core.deps import require_active_user
from app.aris3.db.session import get_db
from app.aris3.schemas.auth import ChangePasswordRequest, ChangePasswordResponse, LoginRequest, TokenResponse
from app.aris3.services.auth import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db=Depends(get_db)):
    service = AuthService(db)
    identifier = payload.email or payload.username_or_email
    user, token = service.login(identifier, payload.password)
    return TokenResponse(access_token=token, must_change_password=user.must_change_password)


@router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user=Depends(require_active_user),
    db=Depends(get_db),
):
    service = AuthService(db)
    user, token = service.change_password(current_user, payload.current_password, payload.new_password)
    return ChangePasswordResponse(access_token=token, must_change_password=user.must_change_password)
