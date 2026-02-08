from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    tenant_id: str
    role: str
    must_change_password: bool
