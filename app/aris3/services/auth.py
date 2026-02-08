from fastapi import HTTPException, status

from app.aris3.core.security import verify_password, get_password_hash, create_access_token
from app.aris3.repos.users import UserRepository


class AuthService:
    def __init__(self, db):
        self.repo = UserRepository(db)

    def login(self, identifier: str, password: str):
        user = self.repo.get_by_username_or_email(identifier)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        token = create_access_token(
            {
                "sub": str(user.id),
                "tenant_id": str(user.tenant_id),
                "role": user.role,
            }
        )
        return user, token

    def change_password(self, user, current_password: str, new_password: str):
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password invalid")
        hashed = get_password_hash(new_password)
        return self.repo.update_password(user, hashed)
