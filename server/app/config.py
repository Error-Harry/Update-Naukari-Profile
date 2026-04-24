"""Typed application settings loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Resolved relative to the process CWD. Listed in order of preference
        # so the last match wins; covers running from repo root or from server/.
        env_file=(
            ".env",
            "naukari_bot/.env",
            "server/.env",
            "server/naukari_bot/.env",
            "../.env",
            "../naukari_bot/.env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Naukri Auto Update"
    app_base_url: str = "http://localhost:8000"

    database_url: str = Field(..., alias="DATABASE_URL")
    jwt_secret: str = Field("change-me-in-production", alias="JWT_SECRET")
    jwt_expire_minutes: int = 60 * 24 * 7
    fernet_key: str = Field(..., alias="FERNET_KEY")

    smtp_email: str = Field(..., alias="SMTP_EMAIL")
    smtp_password: str = Field(..., alias="SMTP_PASSWORD")
    smtp_server: str = Field("smtp.gmail.com", alias="SMTP_SERVER")
    smtp_port: int = Field(587, alias="SMTP_PORT")

    playwright_headed: bool = Field(True, alias="PLAYWRIGHT_HEADED")

    tz: str = "Asia/Kolkata"


@lru_cache
def get_settings() -> Settings:
    return Settings()
