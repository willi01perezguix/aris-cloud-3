from sqlalchemy import func, or_, select

from app.aris3.db.models import User


class UserRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, user_id: str):
        return self.db.get(User, user_id)

    def get_by_id_in_tenant(self, user_id: str, tenant_id: str):
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        return self.db.execute(stmt).scalars().first()

    def list_by_tenant(
        self,
        tenant_id: str,
        *,
        store_scope_id: str | None = None,
        tenant_filter_id: str | None = None,
        store_id: str | None = None,
        role: str | None = None,
        status: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str = "username",
        sort_order: str = "asc",
    ):
        effective_tenant_id = tenant_filter_id or tenant_id
        stmt = select(User).where(User.tenant_id == effective_tenant_id)
        count_stmt = select(func.count()).select_from(User).where(User.tenant_id == effective_tenant_id)

        effective_store_id = store_scope_id or store_id
        if effective_store_id:
            stmt = stmt.where(User.store_id == effective_store_id)
            count_stmt = count_stmt.where(User.store_id == effective_store_id)

        if role:
            normalized_role = role.strip().upper()
            stmt = stmt.where(func.upper(User.role) == normalized_role)
            count_stmt = count_stmt.where(func.upper(User.role) == normalized_role)

        if status:
            normalized_status = status.strip().lower()
            stmt = stmt.where(func.lower(User.status) == normalized_status)
            count_stmt = count_stmt.where(func.lower(User.status) == normalized_status)

        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
            count_stmt = count_stmt.where(User.is_active.is_(is_active))

        if search:
            pattern = f"%{search.strip()}%"
            search_filter = or_(User.username.ilike(pattern), User.email.ilike(pattern))
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        sort_mapping = {
            "username": User.username,
            "email": User.email,
            "created_at": User.created_at,
        }
        sort_column = sort_mapping.get(sort_by, User.created_at)
        stmt = stmt.order_by(sort_column.asc() if sort_order == "asc" else sort_column.desc())

        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)

        rows = self.db.execute(stmt).scalars().all()
        total = self.db.execute(count_stmt).scalar_one()
        return rows, total

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
