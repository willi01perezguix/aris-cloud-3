from sqlalchemy import select

from app.aris3.db.models import ReturnPolicySettings, VariantFieldSettings


class VariantFieldSettingsRepository:
    def __init__(self, db):
        self.db = db

    def get_by_tenant_id(self, tenant_id: str):
        stmt = select(VariantFieldSettings).where(VariantFieldSettings.tenant_id == tenant_id)
        return self.db.execute(stmt).scalars().first()

    def create(self, settings: VariantFieldSettings):
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def update(self, settings: VariantFieldSettings):
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings


class ReturnPolicySettingsRepository:
    def __init__(self, db):
        self.db = db

    def get_by_tenant_id(self, tenant_id: str):
        stmt = select(ReturnPolicySettings).where(ReturnPolicySettings.tenant_id == tenant_id)
        return self.db.execute(stmt).scalars().first()

    def create(self, settings: ReturnPolicySettings):
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def update(self, settings: ReturnPolicySettings):
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings
