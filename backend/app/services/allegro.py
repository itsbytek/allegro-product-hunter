from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from ..models import ApiCache
from .domain import CandidateOffer
from .logging_service import write_log
from .settings_service import (
    ALLEGRO_ACCESS_TOKEN_KEY,
    ALLEGRO_REFRESH_TOKEN_KEY,
    OAUTH_STATE_KEY,
    OAUTH_VERIFIER_KEY,
    SettingsService,
)


class AllegroApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class ListingAccessDenied(AllegroApiError):
    pass


class AsyncRateLimiter:
    def __init__(self, requests_per_second: float):
        self.min_interval = 1 / requests_per_second
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def wait(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_call = time.monotonic()


class AllegroClient:
    accept = "application/vnd.allegro.public.v1+json"

    def __init__(self, db: Session, requests_per_second: float = 2.0):
        self.db = db
        self.config = SettingsService(db)
        self.rate_limiter = AsyncRateLimiter(requests_per_second)

    def _base_urls(self) -> tuple[str, str]:
        setting = self.config.allegro()
        if setting["environment"] == "sandbox":
            return (
                "https://api.allegro.pl.allegrosandbox.pl",
                "https://allegro.pl.allegrosandbox.pl",
            )
        return "https://api.allegro.pl", "https://allegro.pl"

    def _headers(self, token: str) -> dict[str, str]:
        setting = self.config.allegro()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": self.accept,
            "Accept-Language": "pl-PL",
            "User-Agent": setting["user_agent"],
        }

    async def application_token(self, force: bool = False) -> str:
        saved = self.config.get_secret(ALLEGRO_ACCESS_TOKEN_KEY)
        status = self.config.allegro()
        expires_at = status.get("token_expires_at")
        if saved and not force and expires_at:
            try:
                if datetime.fromisoformat(expires_at) > datetime.now(UTC) + timedelta(seconds=30):
                    return saved
            except ValueError:
                pass
        client_id, client_secret = self.config.allegro_credentials()
        if not client_id or not client_secret:
            raise AllegroApiError("Brak Client ID lub Client Secret")
        _, auth_base = self._base_urls()
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{auth_base}/auth/oauth/token",
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {basic}",
                    "User-Agent": status["user_agent"],
                },
            )
        if response.status_code != 200:
            self.config.update_allegro_status(
                last_connection_error=f"OAuth HTTP {response.status_code}"
            )
            raise AllegroApiError("Nie udało się uzyskać tokenu OAuth", response.status_code)
        payload = response.json()
        token = payload["access_token"]
        self.config.set_secret(ALLEGRO_ACCESS_TOKEN_KEY, token)
        self.config.update_allegro_status(
            connected=True,
            token_expires_at=(
                datetime.now(UTC) + timedelta(seconds=payload.get("expires_in", 3600))
            ).isoformat(),
            last_connection_error=None,
        )
        return token

    def authorization_url(self) -> str:
        client_id, _ = self.config.allegro_credentials()
        setting = self.config.allegro()
        if not client_id:
            raise AllegroApiError("Najpierw zapisz Client ID")
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        state = secrets.token_urlsafe(32)
        self.config.set_secret(OAUTH_STATE_KEY, state)
        self.config.set_secret(OAUTH_VERIFIER_KEY, verifier)
        _, auth_base = self._base_urls()
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": setting["redirect_uri"],
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{auth_base}/auth/oauth/authorize?{urlencode(params)}"

    async def exchange_authorization_code(self, code: str, state: str) -> None:
        if not secrets.compare_digest(state, self.config.get_secret(OAUTH_STATE_KEY)):
            raise AllegroApiError("Nieprawidłowy OAuth state")
        setting = self.config.allegro()
        client_id, client_secret = self.config.allegro_credentials()
        _, auth_base = self._base_urls()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": setting["redirect_uri"],
            "code_verifier": self.config.get_secret(OAUTH_VERIFIER_KEY),
        }
        headers = {"User-Agent": setting["user_agent"]}
        if client_secret:
            headers["Authorization"] = (
                "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
            )
        else:
            data["client_id"] = client_id
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{auth_base}/auth/oauth/token", data=data, headers=headers
            )
        if response.status_code != 200:
            raise AllegroApiError("Wymiana kodu OAuth nie powiodła się", response.status_code)
        payload = response.json()
        self.config.set_secret(ALLEGRO_ACCESS_TOKEN_KEY, payload["access_token"])
        if payload.get("refresh_token"):
            self.config.set_secret(ALLEGRO_REFRESH_TOKEN_KEY, payload["refresh_token"])
        self.config.update_allegro_status(
            connected=True,
            token_expires_at=(
                datetime.now(UTC) + timedelta(seconds=payload.get("expires_in", 3600))
            ).isoformat(),
            last_connection_error=None,
        )

    def _cache_key(self, path: str, params: dict[str, Any]) -> str:
        encoded = json.dumps([path, sorted(params.items())], ensure_ascii=False, default=str)
        return hashlib.sha256(encoded.encode()).hexdigest()

    def _cached(self, key: str) -> Any | None:
        row = self.db.get(ApiCache, key)
        if row and row.expires_at.replace(tzinfo=UTC) > datetime.now(UTC):
            return row.payload
        return None

    def _save_cache(self, key: str, payload: Any, ttl_seconds: int = 300) -> None:
        row = self.db.get(ApiCache, key) or ApiCache(key=key)
        row.payload = payload
        row.expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        self.db.add(row)
        self.db.commit()

    async def request(
        self, path: str, params: dict[str, Any], *, cache_ttl: int = 300
    ) -> dict[str, Any]:
        key = self._cache_key(path, params)
        cached = self._cached(key)
        if cached is not None:
            return cached
        token = await self.application_token()
        api_base, _ = self._base_urls()
        retryable = {429, 500, 502, 503, 504}
        last_response: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=httpx.Timeout(25, connect=10)) as client:
            for attempt in range(4):
                await self.rate_limiter.wait()
                try:
                    response = await client.get(
                        f"{api_base}{path}", params=params, headers=self._headers(token)
                    )
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    write_log(
                        self.db,
                        "WARNING",
                        "API_RETRY",
                        f"Ponowienie po błędzie sieci: {type(exc).__name__}",
                        context={"endpoint": path, "attempt": attempt + 1},
                    )
                    if attempt == 3:
                        raise AllegroApiError(
                            f"Błąd sieci Allegro API: {type(exc).__name__}"
                        ) from exc
                    await asyncio.sleep(2**attempt)
                    continue
                last_response = response
                write_log(
                    self.db,
                    "INFO",
                    "API_REQUEST",
                    f"GET {path} → HTTP {response.status_code}",
                    context={
                        "endpoint": path,
                        "status": response.status_code,
                        "attempt": attempt + 1,
                    },
                )
                if response.status_code == 401 and attempt == 0:
                    token = await self.application_token(force=True)
                    continue
                if response.status_code in retryable and attempt < 3:
                    retry_after = min(float(response.headers.get("Retry-After", 2**attempt)), 30)
                    write_log(
                        self.db,
                        "WARNING",
                        "RATE_LIMIT" if response.status_code == 429 else "API_RETRY",
                        f"HTTP {response.status_code}; ponowienie za {retry_after:g} s",
                        context={"endpoint": path, "attempt": attempt + 1},
                    )
                    await asyncio.sleep(retry_after)
                    continue
                break
        if last_response is None:
            raise AllegroApiError("Brak odpowiedzi Allegro API")
        if last_response.status_code == 403:
            try:
                detail = last_response.json()
                code = (detail.get("errors") or [{}])[0].get("code")
            except ValueError:
                code = None
            if code == "VerificationRequired" or "verified" in last_response.text.casefold():
                self.config.update_allegro_status(
                    listing_access="DENIED", last_connection_error="403 VerificationRequired"
                )
                raise ListingAccessDenied(
                    "GET /offers/listing jest dostępne tylko dla zweryfikowanych aplikacji",
                    403,
                    code,
                )
        if last_response.status_code >= 400:
            raise AllegroApiError(
                f"Allegro API HTTP {last_response.status_code}", last_response.status_code
            )
        payload = last_response.json()
        self._save_cache(key, payload, cache_ttl)
        self.config.update_allegro_status(listing_access="GRANTED", last_connection_error=None)
        return payload

    async def listing(
        self, query: str | None, category_id: str | None, limit: int
    ) -> list[CandidateOffer]:
        offers: list[CandidateOffer] = []
        page_size = min(100, limit)
        for offset in range(0, limit, page_size):
            params: dict[str, Any] = {
                "limit": min(page_size, limit - offset),
                "offset": offset,
                "searchMode": "REGULAR",
                "fallback": "false",
                "include": "all",
            }
            if query:
                params["phrase"] = query
            if category_id:
                params["category.id"] = category_id
            if not query and not category_id:
                raise AllegroApiError("Wymagana jest fraza lub category.id")
            payload = await self.request("/offers/listing", params)
            parsed = parse_listing(payload)
            offers.extend(parsed)
            if len(parsed) < params["limit"]:
                break
        return offers


def _money(obj: Any) -> float | None:
    if not isinstance(obj, dict) or obj.get("amount") is None:
        return None
    try:
        return float(obj["amount"])
    except (TypeError, ValueError):
        return None


def parse_listing(payload: dict[str, Any]) -> list[CandidateOffer]:
    result: list[CandidateOffer] = []
    items = payload.get("items") or {}
    for raw in [*(items.get("regular") or []), *(items.get("promoted") or [])]:
        selling = raw.get("sellingMode") or {}
        price = _money(selling.get("price"))
        seller = raw.get("seller") or {}
        if price is None or not raw.get("id") or not seller.get("id"):
            continue
        delivery = raw.get("delivery") or {}
        delivery_price = (
            0.0 if delivery.get("availableForFree") else _money(delivery.get("lowestPrice"))
        )
        images = raw.get("images") or []
        category = raw.get("category") or {}
        stock = raw.get("stock") or {}
        offer_id = str(raw["id"])
        result.append(
            CandidateOffer(
                offer_id=offer_id,
                name=str(raw.get("name") or "Oferta bez nazwy"),
                seller_id=str(seller["id"]),
                seller_login=seller.get("login"),
                seller_company=seller.get("company"),
                seller_super=seller.get("superSeller"),
                price=price,
                delivery_price=delivery_price,
                currency=(selling.get("price") or {}).get("currency", "PLN"),
                url=f"https://allegro.pl/oferta/{offer_id}",
                category_id=str(category.get("id")) if category.get("id") else None,
                image_url=images[0].get("url") if images else None,
                popularity=selling.get("popularity"),
                popularity_range=selling.get("popularityRange"),
                active=True,
                available=stock.get("available"),
                raw=raw,
                source_type="ALLEGRO_API",
                observed_at=datetime.now(UTC),
            )
        )
    return result
