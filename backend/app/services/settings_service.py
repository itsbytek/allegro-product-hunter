from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AppSetting
from ..schemas import AllegroSettingsUpdate, ResearchSettings
from .secrets import SecretStore

RESEARCH_KEY = "research"
ALLEGRO_KEY = "allegro"
ALLEGRO_SECRET_KEY = "allegro_client_secret"
ALLEGRO_ACCESS_TOKEN_KEY = "allegro_access_token"
ALLEGRO_REFRESH_TOKEN_KEY = "allegro_refresh_token"
OAUTH_STATE_KEY = "oauth_state"
OAUTH_VERIFIER_KEY = "oauth_verifier"


class SettingsService:
    def __init__(self, db: Session):
        self.db = db
        self.secrets = SecretStore()
        self.env = get_settings()

    def _get(self, key: str) -> AppSetting | None:
        return self.db.get(AppSetting, key)

    def _put(self, key: str, value: Any = None, encrypted_value: str | None = None) -> None:
        row = self._get(key) or AppSetting(key=key)
        row.value = value
        row.encrypted_value = encrypted_value
        self.db.add(row)
        self.db.commit()

    def research(self) -> ResearchSettings:
        row = self._get(RESEARCH_KEY)
        return ResearchSettings.model_validate(row.value if row and row.value else {})

    def save_research(self, settings: ResearchSettings) -> ResearchSettings:
        self._put(RESEARCH_KEY, settings.model_dump(mode="json"))
        return settings

    def allegro(self) -> dict[str, Any]:
        row = self._get(ALLEGRO_KEY)
        saved = row.value if row and row.value else {}
        secret_configured = bool(
            self.get_secret(ALLEGRO_SECRET_KEY) or self.env.allegro_client_secret
        )
        token_configured = bool(self.get_secret(ALLEGRO_ACCESS_TOKEN_KEY))
        return {
            "client_id": saved.get("client_id") or self.env.allegro_client_id,
            "client_secret_configured": secret_configured,
            "redirect_uri": saved.get("redirect_uri") or self.env.allegro_redirect_uri,
            "environment": saved.get("environment") or self.env.allegro_environment,
            "user_agent": saved.get("user_agent") or self.env.allegro_user_agent,
            "connected": token_configured,
            "listing_access": saved.get("listing_access", "UNKNOWN"),
            "last_connection_error": saved.get("last_connection_error"),
            "token_expires_at": saved.get("token_expires_at"),
        }

    def save_allegro(self, update: AllegroSettingsUpdate) -> dict[str, Any]:
        current = self.allegro()
        payload = {
            "client_id": update.client_id.strip(),
            "redirect_uri": update.redirect_uri.strip(),
            "environment": update.environment,
            "user_agent": update.user_agent.strip(),
            "listing_access": current.get("listing_access", "UNKNOWN"),
            "last_connection_error": current.get("last_connection_error"),
            "token_expires_at": current.get("token_expires_at"),
        }
        self._put(ALLEGRO_KEY, payload)
        if update.client_secret:
            self.set_secret(ALLEGRO_SECRET_KEY, update.client_secret)
        return self.allegro()

    def update_allegro_status(self, **changes: Any) -> None:
        row = self._get(ALLEGRO_KEY)
        payload = dict(row.value if row and row.value else {})
        payload.update(changes)
        self._put(ALLEGRO_KEY, payload)

    def set_secret(self, key: str, value: str) -> None:
        self._put(key, encrypted_value=self.secrets.encrypt(key, value))

    def get_secret(self, key: str) -> str:
        row = self._get(key)
        if not row or not row.encrypted_value:
            return ""
        return self.secrets.decrypt(key, row.encrypted_value)

    def allegro_credentials(self) -> tuple[str, str]:
        config = self.allegro()
        secret = self.get_secret(ALLEGRO_SECRET_KEY) or self.env.allegro_client_secret
        return config["client_id"], secret
