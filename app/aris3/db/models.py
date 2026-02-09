from datetime import datetime

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.aris3.db.base import Base, GUID


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    stores = relationship("Store", back_populates="tenant")
    users = relationship("User", back_populates="tenant")
    role_templates = relationship("RoleTemplate", back_populates="tenant")


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="stores")
    users = relationship("User", back_populates="store")

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_store_tenant_name"),)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=False)
    store_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("stores.id"), index=True, nullable=True)
    username: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="users")
    store = relationship("Store", back_populates="users")

    __table_args__ = (
        UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )


class VariantFieldSettings(Base):
    __tablename__ = "variant_field_settings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=False)
    var1_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    var2_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("tenant_id", name="uq_variant_field_settings_tenant_id"),)


class ReturnPolicySettings(Base):
    __tablename__ = "return_policy_settings"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=False)
    return_window_days: Mapped[int] = mapped_column(nullable=False, default=30)
    require_receipt: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_refund_cash: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_refund_card: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_refund_transfer: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_exchange: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    require_manager_for_exceptions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepted_conditions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    non_reusable_label_strategy: Mapped[str] = mapped_column(String(50), nullable=False, default="ASSIGN_NEW_EPC")
    restocking_fee_pct: Mapped[float] = mapped_column(nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("tenant_id", name="uq_return_policy_settings_tenant_id"),)


class StockItem(Base):
    __tablename__ = "stock_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    var1_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    var2_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    epc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pool: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location_is_vendible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_thumb_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("tenant_id", "epc", name="uq_stock_items_tenant_epc"),)


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=False)
    origin_store_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("stores.id"), index=True, nullable=False)
    destination_store_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("stores.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    dispatched_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    canceled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TransferLine(Base):
    __tablename__ = "transfer_lines"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    transfer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("transfers.id"), index=True, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=False)
    line_type: Mapped[str] = mapped_column(String(20), nullable=False)
    qty: Mapped[int] = mapped_column(nullable=False, default=1)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    var1_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    var2_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    epc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pool: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location_is_vendible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_thumb_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TransferMovement(Base):
    __tablename__ = "transfer_movements"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=False)
    transfer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("transfers.id"), index=True, nullable=False)
    transfer_line_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("transfer_lines.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    from_location_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    from_pool: Mapped[str | None] = mapped_column(String(100), nullable=True)
    to_location_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    to_pool: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qty: Mapped[int] = mapped_column(nullable=False, default=1)
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PermissionCatalog(Base):
    __tablename__ = "permission_catalog"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    role_template_permissions = relationship("RoleTemplatePermission", back_populates="permission")


class RoleTemplate(Base):
    __tablename__ = "role_templates"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    tenant = relationship("Tenant", back_populates="role_templates")
    permissions = relationship("RoleTemplatePermission", back_populates="role_template")

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_role_templates_tenant_name"),)


class RoleTemplatePermission(Base):
    __tablename__ = "role_template_permissions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    role_template_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("role_templates.id"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("permission_catalog.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    role_template = relationship("RoleTemplate", back_populates="permissions")
    permission = relationship("PermissionCatalog", back_populates="role_template_permissions")

    __table_args__ = (
        UniqueConstraint("role_template_id", "permission_id", name="uq_role_template_permission"),
    )


class TenantRolePolicy(Base):
    __tablename__ = "tenant_role_policies"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=True)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    permission_code: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    effect: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "role_name",
            "permission_code",
            name="uq_tenant_role_policy_permission",
        ),
    )


class StoreRolePolicy(Base):
    __tablename__ = "store_role_policies"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("stores.id"), index=True, nullable=False)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    permission_code: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    effect: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "store_id",
            "role_name",
            "permission_code",
            name="uq_store_role_policy_permission",
        ),
    )


class UserPermissionOverride(Base):
    __tablename__ = "user_permission_overrides"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenants.id"), index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), index=True, nullable=False)
    permission_code: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    effect: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "permission_code",
            name="uq_user_permission_override",
        ),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False, default="POST")
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    status_code: Mapped[int | None] = mapped_column(nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "endpoint", "method", "idempotency_key", name="uq_idempotency"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True, nullable=True)
    store_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entity: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(255), nullable=False, default="unknown")
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    before_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    result: Mapped[str] = mapped_column(String(50), nullable=False, default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PosSale(Base):
    __tablename__ = "pos_sales"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")
    total_due: Mapped[float] = mapped_column(nullable=False, default=0.0)
    paid_total: Mapped[float] = mapped_column(nullable=False, default=0.0)
    balance_due: Mapped[float] = mapped_column(nullable=False, default=0.0)
    change_due: Mapped[float] = mapped_column(nullable=False, default=0.0)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    checked_out_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    canceled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PosSaleLine(Base):
    __tablename__ = "pos_sale_lines"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    line_type: Mapped[str] = mapped_column(String(20), nullable=False)
    qty: Mapped[int] = mapped_column(nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column(nullable=False, default=0.0)
    line_total: Mapped[float] = mapped_column(nullable=False, default=0.0)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    var1_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    var2_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    epc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pool: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location_is_vendible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_thumb_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    image_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PosReturnEvent(Base):
    __tablename__ = "pos_return_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    sale_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    exchange_sale_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    refund_subtotal: Mapped[float] = mapped_column(nullable=False, default=0.0)
    restocking_fee: Mapped[float] = mapped_column(nullable=False, default=0.0)
    refund_total: Mapped[float] = mapped_column(nullable=False, default=0.0)
    exchange_total: Mapped[float] = mapped_column(nullable=False, default=0.0)
    net_adjustment: Mapped[float] = mapped_column(nullable=False, default=0.0)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PosPayment(Base):
    __tablename__ = "pos_payments"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False, default=0.0)
    authorization_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    voucher_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PosCashSession(Base):
    __tablename__ = "pos_cash_sessions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    cashier_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PosCashMovement(Base):
    __tablename__ = "pos_cash_movements"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    store_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    cash_session_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True, nullable=False)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


Index("ix_users_tenant_username", User.tenant_id, User.username)
Index("ix_users_tenant_email", User.tenant_id, User.email)
