from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel

from app.aris3.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/aris3/auth/token")


class TokenData(BaseModel):
    sub: str
    tenant_id: str | None = None
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
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
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


__all__ = [
    "TokenData",
    "oauth2_scheme",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_user_access_token",
    "decode_token",
]
