"""Application configuration via environment variables."""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "BIC-CCD"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Oracle Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 1521
    DB_SERVICE: str = "XEPDB1"
    DB_USER: str = "bic_ccd"
    DB_PASSWORD: str = "bic_ccd_pass"
    DB_POOL_MIN: int = 2
    DB_POOL_MAX: int = 10
    DB_POOL_INCREMENT: int = 1

    # For SQLite fallback (development without Oracle)
    USE_SQLITE: bool = True
    SQLITE_URL: str = "sqlite:///./bic_ccd.db"

    # S3 / Object Storage
    S3_ENDPOINT: Optional[str] = None
    S3_BUCKET: str = "bic-ccd-evidence"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"

    # SMTP
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "bic-ccd@company.com"
    SMTP_TLS: bool = True

    # Auth
    JWT_SECRET: str = "jwt-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480

    # Scheduler
    SCHEDULER_ENABLED: bool = True

    @property
    def database_url(self) -> str:
        if self.USE_SQLITE:
            return self.SQLITE_URL
        return f"oracle+oracledb://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/?service_name={self.DB_SERVICE}"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
