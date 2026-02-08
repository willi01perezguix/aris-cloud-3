from sqlalchemy import select

from app.aris3.db.models import User


class UserRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, user_id: str):
        return self.db.get(User, user_id)

    def get_by_username_or_email(self, identifier: str):
        stmt = select(User).where((User.username == identifier) | (User.email == identifier))
        return self.db.execute(stmt).scalars().first()

    def update_password(self, user: User, hashed_password: str):
        user.hashed_password = hashed_password
        user.must_change_password = False
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
