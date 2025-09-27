from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings.

    Loads from environment with safe local defaults.
    """

    app_name: str = Field(default="sms-foundation-agent")
    app_env: Literal["local", "dev", "staging", "prod"] = Field(default="local", alias="APP_ENV")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    twilio_auth_token: str = Field(default="", alias="TWILIO_AUTH_TOKEN")
    twilio_account_sid: str = Field(default="", alias="TWILIO_ACCOUNT_SID")
    twilio_phone_number: str = Field(default="", alias="TWILIO_PHONE_NUMBER")
    # Database URL for async SQLAlchemy engine. Default to local SQLite file for dev/test.
    database_url: str = Field(default="sqlite+aiosqlite:///./app.db", alias="DATABASE_URL")
    # Collections Monitor base URL for tenant lookup
    monitor_api_url: str = Field(default="", alias="MONITOR_API_URL")
    # Tenant Profile base URL for updating language preferences
    tenant_profile_api_url: str = Field(default="", alias="TENANT_PROFILE_API_URL")
    # Outbound send retry/backoff settings
    twilio_send_max_retries: int = Field(default=3, alias="TWILIO_SEND_MAX_RETRIES")
    twilio_send_base_backoff_ms: int = Field(default=100, alias="TWILIO_SEND_BASE_BACKOFF_MS")
    twilio_send_backoff_cap_ms: int = Field(default=2000, alias="TWILIO_SEND_BACKOFF_CAP_MS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()  # type: ignore[call-arg]
