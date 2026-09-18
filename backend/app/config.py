from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    app_env: str = "development"
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'allegro_hunter.db').as_posix()}"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    frontend_url: str = "http://localhost:5173"
    log_level: str = "INFO"

    allegro_client_id: str = ""
    allegro_client_secret: str = ""
    allegro_redirect_uri: str = "http://localhost:8000/api/allegro/oauth/callback"
    allegro_environment: str = "production"
    allegro_user_agent: str = (
        "AllegroProductHunter/0.1 (local application; contact: configure-in-env)"
    )
    app_encryption_key: str = ""

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allegro_api_url(self) -> str:
        if self.allegro_environment == "sandbox":
            return "https://api.allegro.pl.allegrosandbox.pl"
        return "https://api.allegro.pl"

    @property
    def allegro_auth_url(self) -> str:
        if self.allegro_environment == "sandbox":
            return "https://allegro.pl.allegrosandbox.pl"
        return "https://allegro.pl"


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
