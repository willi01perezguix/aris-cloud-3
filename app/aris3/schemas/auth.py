from pydantic import BaseModel, EmailStr, Field, model_validator


class LoginRequest(BaseModel):
    email: EmailStr | None = None
    username_or_email: str | None = Field(default=None, alias="username_or_email")
    password: str

    @model_validator(mode="after")
    def ensure_identifier(self):
        if not self.email and not self.username_or_email:
            raise ValueError("email is required")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool


class ChangePasswordResponse(BaseModel):
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
    store_id: str | None = None
    role: str
    status: str
    is_active: bool
    must_change_password: bool
