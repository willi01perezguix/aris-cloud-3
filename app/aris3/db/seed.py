from sqlalchemy import select

from app.aris3.core.config import settings
from app.aris3.core.security import get_password_hash
from app.aris3.db.models import (
    PermissionCatalog,
    RoleTemplate,
    RoleTemplatePermission,
    Store,
    Tenant,
    User,
)


DEFAULT_PERMISSIONS = [
    ("TENANT_VIEW", "View tenant details"),
    ("STORE_VIEW", "View store details"),
    ("STORE_MANAGE", "Manage store details"),
    ("USER_MANAGE", "Manage users"),
    ("SETTINGS_MANAGE", "Manage tenant settings"),
    ("AUDIT_VIEW", "View audit events"),
    ("TRANSFER_VIEW", "View transfers"),
    ("TRANSFER_MANAGE", "Manage transfers"),
]

DEFAULT_ROLE_TEMPLATES = {
    "SUPERADMIN": [
        "TENANT_VIEW",
        "STORE_VIEW",
        "STORE_MANAGE",
        "USER_MANAGE",
        "SETTINGS_MANAGE",
        "AUDIT_VIEW",
        "TRANSFER_VIEW",
        "TRANSFER_MANAGE",
    ],
    "ADMIN": [
        "TENANT_VIEW",
        "STORE_VIEW",
        "STORE_MANAGE",
        "USER_MANAGE",
        "SETTINGS_MANAGE",
        "AUDIT_VIEW",
        "TRANSFER_VIEW",
        "TRANSFER_MANAGE",
    ],
    "MANAGER": ["STORE_VIEW", "USER_MANAGE", "TRANSFER_VIEW", "TRANSFER_MANAGE"],
    "USER": ["STORE_VIEW", "TRANSFER_VIEW"],
}


def _get_or_create_tenant(db):
    tenant = db.execute(select(Tenant).where(Tenant.name == settings.DEFAULT_TENANT_NAME)).scalars().first()
    if tenant:
        return tenant
    tenant = Tenant(name=settings.DEFAULT_TENANT_NAME)
    db.add(tenant)
    db.flush()
    return tenant


def _get_or_create_store(db, tenant):
    store = (
        db.execute(
            select(Store).where(Store.tenant_id == tenant.id, Store.name == settings.DEFAULT_STORE_NAME)
        )
        .scalars()
        .first()
    )
    if store:
        return store
    store = Store(tenant_id=tenant.id, name=settings.DEFAULT_STORE_NAME)
    db.add(store)
    db.flush()
    return store


def _get_or_create_permissions(db):
    existing = {perm.code: perm for perm in db.execute(select(PermissionCatalog)).scalars().all()}
    for code, description in DEFAULT_PERMISSIONS:
        if code in existing:
            continue
        db.add(PermissionCatalog(code=code, description=description))


def _get_or_create_role_templates(db):
    existing = {
        role.name: role
        for role in db.execute(select(RoleTemplate).where(RoleTemplate.tenant_id.is_(None))).scalars().all()
    }
    for name in DEFAULT_ROLE_TEMPLATES.keys():
        if name in existing:
            continue
        db.add(RoleTemplate(name=name, description=f"System role: {name}", is_system=True))


def _assign_role_permissions(db):
    permissions = {perm.code: perm for perm in db.execute(select(PermissionCatalog)).scalars().all()}
    roles = {
        role.name: role
        for role in db.execute(select(RoleTemplate).where(RoleTemplate.tenant_id.is_(None))).scalars().all()
    }
    existing_pairs = {
        (rtp.role_template_id, rtp.permission_id)
        for rtp in db.execute(select(RoleTemplatePermission)).scalars().all()
    }
    for role_name, permission_codes in DEFAULT_ROLE_TEMPLATES.items():
        role = roles.get(role_name)
        if not role:
            continue
        for code in permission_codes:
            permission = permissions.get(code)
            if not permission:
                continue
            pair = (role.id, permission.id)
            if pair in existing_pairs:
                continue
            db.add(RoleTemplatePermission(role_template_id=role.id, permission_id=permission.id))


def _get_or_create_superadmin(db, tenant, store):
    user = (
        db.execute(select(User).where(User.username == settings.SUPERADMIN_USERNAME, User.tenant_id == tenant.id))
        .scalars()
        .first()
    )
    if user:
        return user
    user = User(
        tenant_id=tenant.id,
        store_id=store.id,
        username=settings.SUPERADMIN_USERNAME,
        email=settings.SUPERADMIN_EMAIL,
        hashed_password=get_password_hash(settings.SUPERADMIN_PASSWORD),
        role="SUPERADMIN",
        status="active",
        must_change_password=False,
        is_active=True,
    )
    db.add(user)
    return user


def run_seed(db):
    tenant = _get_or_create_tenant(db)
    store = _get_or_create_store(db, tenant)
    _get_or_create_permissions(db)
    _get_or_create_role_templates(db)
    db.flush()
    _assign_role_permissions(db)
    _get_or_create_superadmin(db, tenant, store)
    db.commit()
