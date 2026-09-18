from __future__ import annotations

import os

import keyring
from cryptography.fernet import Fernet, InvalidToken

from ..config import BASE_DIR, get_settings


class SecretStoreError(RuntimeError):
    pass


class SecretStore:
    """Uses Windows Credential Manager, with encrypted-file fallback for service contexts."""

    def __init__(self, service_name: str = "Allegro Product Hunter") -> None:
        self.service_name = service_name
        self.key_path = BASE_DIR / "data" / ".encryption.key"

    def _fernet(self) -> Fernet:
        configured = get_settings().app_encryption_key.strip()
        if configured:
            try:
                return Fernet(configured.encode("ascii"))
            except (ValueError, TypeError) as exc:
                raise SecretStoreError("APP_ENCRYPTION_KEY is not a valid Fernet key") from exc
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
            try:
                os.chmod(self.key_path, 0o600)
                if os.name == "nt":
                    import ctypes

                    ctypes.windll.kernel32.SetFileAttributesW(str(self.key_path), 0x2)
            except OSError:
                pass
        return Fernet(self.key_path.read_bytes().strip())

    def encrypt(self, key: str, value: str) -> str:
        if not value:
            return ""
        try:
            keyring.set_password(self.service_name, key, value)
            # Some Windows keyring backends accept writes but do not persist or
            # return them in the next process. Verify the round-trip before
            # recording a keyring marker; otherwise use the encrypted fallback.
            if keyring.get_password(self.service_name, key) == value:
                return f"keyring:{key}"
        except Exception:
            pass
        encrypted = self._fernet().encrypt(value.encode("utf-8")).decode("ascii")
        return f"fernet:{encrypted}"

    def decrypt(self, key: str, marker: str | None) -> str:
        if not marker:
            return ""
        if marker.startswith("keyring:"):
            try:
                return keyring.get_password(self.service_name, key) or ""
            except Exception as exc:
                raise SecretStoreError("Windows Credential Manager is unavailable") from exc
        if marker.startswith("fernet:"):
            try:
                return (
                    self._fernet().decrypt(marker.removeprefix("fernet:").encode()).decode("utf-8")
                )
            except InvalidToken as exc:
                raise SecretStoreError("Local encrypted secret cannot be decrypted") from exc
        raise SecretStoreError("Unknown secret storage format")
