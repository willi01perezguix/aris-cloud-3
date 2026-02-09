from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ARIS-CLOUD-3"
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = "sqlite+pysqlite:///./aris3.db"
    DEFAULT_TENANT_NAME: str = "Default Tenant"
    DEFAULT_STORE_NAME: str = "Default Store"
    SUPERADMIN_USERNAME: str = "superadmin"
    SUPERADMIN_EMAIL: str = "superadmin@example.com"
    SUPERADMIN_PASSWORD: str = "change-me"
    EXPORTS_STORAGE_PATH: str = "./exports_storage"

    class Config:
        env_file = ".env"


settings = Settings()
