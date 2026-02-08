from fastapi import HTTPException, status

from app.aris3.core.security import verify_password, get_password_hash, create_user_access_token
from app.aris3.repos.users import UserRepository


class AuthService:
    def __init__(self, db):
        self.repo = UserRepository(db)

    def login(self, identifier: str, password: str):
        candidates = self.repo.list_by_username_or_email(identifier)
        if not candidates:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        inactive_match = None
        for user in candidates:
            if not verify_password(password, user.hashed_password):
                continue
            try:
                self._ensure_user_active(user)
            except HTTPException:
                inactive_match = user
                continue
            token = create_user_access_token(user)
            return user, token

        if inactive_match is not None:
            self._ensure_user_active(inactive_match)

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    def change_password(self, user, current_password: str, new_password: str):
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password invalid")
        self._validate_new_password(user, current_password, new_password)
        hashed = get_password_hash(new_password)
        updated_user = self.repo.update_password(user, hashed)
        return updated_user, create_user_access_token(updated_user)

    @staticmethod
    def _ensure_user_active(user) -> None:
        if not user.is_active or user.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive or suspended")

    @staticmethod
    def _validate_new_password(user, current_password: str, new_password: str) -> None:
        if len(new_password) < 8:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too short")
        if new_password == current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must differ from current password",
            )
        has_letter = any(char.isalpha() for char in new_password)
        has_digit = any(char.isdigit() for char in new_password)
        if not (has_letter and has_digit):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must include letters and numbers",
            )
