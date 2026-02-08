from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ARIS-CLOUD-3"
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = "sqlite+pysqlite:///./aris3.db"

    class Config:
        env_file = ".env"


settings = Settings()
