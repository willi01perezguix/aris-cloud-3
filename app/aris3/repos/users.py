from sqlalchemy import select

from app.aris3.db.models import User


class UserRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, user_id: str):
        return self.db.get(User, user_id)

    def get_by_id_in_tenant(self, user_id: str, tenant_id: str):
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        return self.db.execute(stmt).scalars().first()

    def list_by_tenant(self, tenant_id: str, store_id: str | None = None):
        stmt = select(User).where(User.tenant_id == tenant_id)
        if store_id:
            stmt = stmt.where(User.store_id == store_id)
        stmt = stmt.order_by(User.username)
        return self.db.execute(stmt).scalars().all()

    def get_by_username_or_email(self, identifier: str):
        stmt = select(User).where((User.username == identifier) | (User.email == identifier))
        return self.db.execute(stmt).scalars().first()

    def list_by_username_or_email(self, identifier: str):
        stmt = select(User).where((User.username == identifier) | (User.email == identifier))
        return self.db.execute(stmt).scalars().all()

    def update_password(self, user: User, hashed_password: str):
        user.hashed_password = hashed_password
        user.must_change_password = False
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
