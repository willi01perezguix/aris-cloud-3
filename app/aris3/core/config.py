from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

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
    REPORTS_MAX_DATE_RANGE_DAYS: int = 92
    EXPORTS_MAX_ROWS: int = 31
    EXPORTS_LIST_MAX_PAGE_SIZE: int = 200
    OPS_ENABLE_INTEGRITY_SCAN: bool = True
    OPS_ENABLE_BACKUP_DRILL: bool = True
    OPS_DRILL_TIMEOUT_SEC: int = 120
    OPS_ARTIFACTS_DIR: str = "./artifacts"
    METRICS_ENABLED: bool = True
    ARIS3_SPACES_ACCESS_KEY: str = ""
    ARIS3_SPACES_SECRET_KEY: str = ""
    ARIS3_SPACES_BUCKET: str = ""
    ARIS3_SPACES_REGION: str = ""
    ARIS3_SPACES_ENDPOINT: str = ""
    ARIS3_SPACES_ORIGIN_BASE_URL: str = ""
    ARIS3_SPACES_CDN_BASE_URL: str = ""
    ARIS3_IMAGE_SOURCE: str = "digitalocean_spaces"

settings = Settings()
