from pydantic import BaseModel, EmailStr, model_validator


class LoginRequest(BaseModel):
    email: EmailStr | None = None
    username_or_email: str | None = None
    password: str

    @model_validator(mode="after")
    def ensure_identifier(self):
        if not self.email and not self.username_or_email:
            raise ValueError("email or username_or_email is required")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool
    trace_id: str


class ChangePasswordResponse(BaseModel):
    ok: bool
    message: str
    trace_id: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    tenant_id: str
    store_id: str | None = None
    role: str
    status: str
    is_active: bool
    must_change_password: bool
    trace_id: str
