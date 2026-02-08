from fastapi import APIRouter, Depends

from app.aris3.core.security import get_current_user
from app.aris3.db.session import get_db
from app.aris3.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse
from app.aris3.services.auth import AuthService

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db=Depends(get_db)):
    service = AuthService(db)
    user, token = service.login(payload.username_or_email, payload.password)
    return TokenResponse(access_token=token, must_change_password=user.must_change_password)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    service = AuthService(db)
    user = service.change_password(current_user, payload.current_password, payload.new_password)
    return {"status": "changed", "must_change_password": user.must_change_password}
