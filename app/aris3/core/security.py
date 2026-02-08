from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, ValidationError

from app.aris3.core.config import settings
from app.aris3.db.session import get_db
from app.aris3.repos.users import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/aris3/auth/login")


class TokenData(BaseModel):
    sub: str
    tenant_id: str
    store_id: str | None = None
    role: str
    status: str
    is_active: bool
    must_change_password: bool
    email: str
    username: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

def create_user_access_token(user, expires_delta: Optional[timedelta] = None) -> str:
    return create_access_token(
        {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "store_id": str(user.store_id) if user.store_id else None,
            "role": user.role,
            "status": user.status,
            "is_active": user.is_active,
            "must_change_password": user.must_change_password,
            "email": user.email,
            "username": user.username,
        },
        expires_delta=expires_delta,
    )


def get_current_token_data(token: str = Depends(oauth2_scheme)) -> TokenData:
    try:
        payload = decode_token(token)
        return TokenData(**payload)
    except (JWTError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def get_current_user(token_data: TokenData = Depends(get_current_token_data), db=Depends(get_db)):
    try:
        user_id = token_data.sub
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except AttributeError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    repo = UserRepository(db)
    user = repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if not user.is_active or user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive or suspended")
    return user
