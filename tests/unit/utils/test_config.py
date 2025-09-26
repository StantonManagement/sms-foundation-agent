import os

from src.utils.config import Settings, get_settings


def test_settings_defaults_local_env_and_version(monkeypatch):
    # Clear env to test defaults
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("APP_VERSION", raising=False)

    # Create a fresh instance (bypass cache)
    s = Settings()
    assert s.app_env == "local"
    assert s.app_version == "0.1.0"


def test_settings_respects_env_vars(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("APP_VERSION", "9.9.9")

    # Bypass cache by constructing directly
    s = Settings()
    assert s.app_env == "dev"
    assert s.app_version == "9.9.9"

