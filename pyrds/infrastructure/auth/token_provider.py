from __future__ import annotations

import asyncio
import threading
import time
from os.path import isabs
from pathlib import Path
from typing import Any, Mapping

import httpx

from pyrds.domain.exceptions import AuthError, ConfigError
from pyrds.infrastructure.config.settings import ApiClientSettings


def resolve_certificate_path(certificate: str | None) -> bool | str:
    if not certificate:
        return True
    if isabs(certificate):
        return certificate
    package_relative = Path(__file__).resolve().parents[2] / certificate
    if package_relative.exists():
        return str(package_relative)
    return str(Path(certificate).expanduser().resolve())


def pick_proxy(proxies: Mapping[str, str] | None) -> str | None:
    if not proxies:
        return None
    if proxies.get("https://"):
        return proxies["https://"]
    if proxies.get("http://"):
        return proxies["http://"]
    for value in proxies.values():
        if value:
            return value
    return None


class TokenProvider:
    def __init__(self, refresh_skew_seconds: int = 60) -> None:
        self._token: str | None = None
        self._expires_at_epoch: float = 0.0
        self._refresh_skew_seconds = refresh_skew_seconds
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()

    def get_token(self) -> str:
        if self._is_valid():
            return self._require_token()

        with self._sync_lock:
            if self._is_valid():
                return self._require_token()
            token, expires_at = self._fetch_token_sync()
            self._token = token
            self._expires_at_epoch = expires_at
            return token

    async def get_token_async(self) -> str:
        if self._is_valid():
            return self._require_token()

        async with self._async_lock:
            if self._is_valid():
                return self._require_token()
            token, expires_at = await self._fetch_token_async()
            self._token = token
            self._expires_at_epoch = expires_at
            return token

    def invalidate(self) -> None:
        self._token = None
        self._expires_at_epoch = 0.0

    def _is_valid(self) -> bool:
        return (
            self._token is not None
            and time.time() < (self._expires_at_epoch - self._refresh_skew_seconds)
        )

    def _require_token(self) -> str:
        if not self._token:
            raise AuthError("Token is not available.")
        return self._token

    def _fetch_token_sync(self) -> tuple[str, float]:
        raise NotImplementedError

    async def _fetch_token_async(self) -> tuple[str, float]:
        raise NotImplementedError


class StaticTokenProvider(TokenProvider):
    def __init__(self, token: str) -> None:
        super().__init__(refresh_skew_seconds=0)
        self._token = token
        self._expires_at_epoch = time.time() + 365 * 24 * 3600

    def _fetch_token_sync(self) -> tuple[str, float]:
        return self._require_token(), self._expires_at_epoch

    async def _fetch_token_async(self) -> tuple[str, float]:
        return self._require_token(), self._expires_at_epoch


class OAuth2ClientCredentialsTokenProvider(TokenProvider):
    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        grant_type: str = "client_credentials",
        scope: list[str] | None = None,
        verify: bool | str = True,
        proxies: Mapping[str, str] | None = None,
        refresh_skew_seconds: int = 60,
    ) -> None:
        super().__init__(refresh_skew_seconds=refresh_skew_seconds)
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._grant_type = grant_type or "client_credentials"
        self._scope = scope or []
        self._verify = verify
        self._proxy = pick_proxy(proxies)

    def _payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"grant_type": self._grant_type}
        if self._scope:
            payload["scope"] = " ".join(self._scope)
        return payload

    def _fetch_token_sync(self) -> tuple[str, float]:
        try:
            with httpx.Client(
                verify=self._verify,
                proxy=self._proxy,
                timeout=15.0,
                headers={"Accept": "application/json"},
            ) as client:
                response = client.post(
                    self._token_url,
                    data=self._payload(),
                    auth=(self._client_id, self._client_secret),
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise AuthError(f"OAuth2 token request failed: {exc}") from exc

        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not token:
            raise AuthError("OAuth2 token response missing 'access_token'.")
        return token, time.time() + expires_in

    async def _fetch_token_async(self) -> tuple[str, float]:
        try:
            async with httpx.AsyncClient(
                verify=self._verify,
                proxy=self._proxy,
                timeout=15.0,
                headers={"Accept": "application/json"},
            ) as client:
                response = await client.post(
                    self._token_url,
                    data=self._payload(),
                    auth=(self._client_id, self._client_secret),
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise AuthError(f"OAuth2 token request failed: {exc}") from exc

        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not token:
            raise AuthError("OAuth2 token response missing 'access_token'.")
        return token, time.time() + expires_in


def build_token_provider(settings: ApiClientSettings) -> TokenProvider | None:
    auth = settings.authentication
    auth_type = auth.type.strip().lower()

    if auth_type in {"none", ""}:
        return None

    if auth_type in {"token", "token_based", "token-based"}:
        token = auth.resolved_token(settings.env)
        if not token:
            raise ConfigError(f"No token found for env '{settings.env}'.")
        return StaticTokenProvider(token=token)

    if auth_type in {"oauth2", "oauth"}:
        if not auth.token_url:
            raise ConfigError("authentication.token_url is required for OAuth2.")
        if not auth.client_id:
            raise ConfigError("authentication.client_id is required for OAuth2.")
        if not auth.client_secret:
            raise ConfigError("authentication.client_secret is required for OAuth2.")
        return OAuth2ClientCredentialsTokenProvider(
            token_url=auth.token_url,
            client_id=auth.client_id,
            client_secret=auth.client_secret,
            grant_type=auth.grant_type,
            scope=auth.scope,
            verify=resolve_certificate_path(auth.certificate),
            proxies=settings.proxies,
        )

    raise ConfigError(f"Unsupported authentication.type: {auth.type}")
