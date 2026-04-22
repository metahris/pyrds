from __future__ import annotations

import asyncio
import random
import time
from typing import Any, Mapping
from urllib.parse import quote, urljoin

import httpx

from pyrds.domain.exceptions import (
    BatchRequestError,
    ClientClosedError,
    ConfigError,
    NonRetryableAPIError,
    RequestTimeoutError,
    RetryableAPIError,
    TransportError,
    UnexpectedResponseError,
)
from pyrds.infrastructure.auth.token_provider import (
    build_token_provider,
    pick_proxy,
    resolve_certificate_path,
)
from pyrds.infrastructure.config.settings import ApiClientSettings


class NullLogger:
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass


class BaseAPI:
    RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
    SAFE_RETRY_METHODS = {"GET", "DELETE"}

    def __init__(
        self,
        *,
        logger: Any | None,
        settings: ApiClientSettings,
        semaphore: int | None = None,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        max_retries: int = 4,
        base_retry_delay: float = 0.25,
        max_retry_delay: float = 4.0,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self.logger = logger or NullLogger()
        self._settings = settings
        self._max_retries = max_retries
        self._base_retry_delay = base_retry_delay
        self._max_retry_delay = max_retry_delay
        self._async_concurrency = semaphore or 20

        self._base_url = self._build_base_url(settings)
        self._verify = resolve_certificate_path(settings.authentication.certificate)
        self._proxy = pick_proxy(settings.proxies)
        self._token_provider = build_token_provider(settings)

        headers = {"Accept": "application/json"}
        if default_headers:
            headers.update(default_headers)

        limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )

        self._sync_client = httpx.Client(
            verify=self._verify,
            proxy=self._proxy,
            timeout=None,
            limits=limits,
            headers=headers,
        )
        self._async_client = httpx.AsyncClient(
            verify=self._verify,
            proxy=self._proxy,
            timeout=None,
            limits=limits,
            headers=headers,
        )

        self._closed = False
        self._async_closed = False
        self._semaphore: asyncio.Semaphore | None = None
        self._semaphore_loop: asyncio.AbstractEventLoop | None = None

    @staticmethod
    def _build_base_url(settings: ApiClientSettings) -> str:
        host = settings.resolved_host.strip()
        if not host:
            raise ConfigError("Host is empty.")

        if host.startswith("http://") or host.startswith("https://"):
            return f"{host.rstrip('/')}:{settings.port}"

        return f"https://{host.rstrip('/')}:{settings.port}"

    def _ensure_open_sync(self) -> None:
        if self._closed:
            raise ClientClosedError("Synchronous client is closed.")

    def _ensure_open_async(self) -> None:
        if self._async_closed:
            raise ClientClosedError("Asynchronous client is closed.")

    def _get_semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._semaphore_loop is not loop:
            self._semaphore = asyncio.Semaphore(self._async_concurrency)
            self._semaphore_loop = loop
        return self._semaphore

    def close(self) -> None:
        if not self._closed:
            self._sync_client.close()
            self._closed = True

    async def aclose(self) -> None:
        if not self._async_closed:
            await self._async_client.aclose()
            self._async_closed = True

    def __enter__(self) -> "BaseAPI":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    async def __aenter__(self) -> "BaseAPI":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    def _build_url(self, endpoint: str = "") -> str:
        base = self._base_url.rstrip("/") + "/"
        relative = endpoint.strip("/")
        return urljoin(base, relative)

    def _get_auth_headers(self) -> dict[str, str]:
        if not self._token_provider:
            return {}
        return {"AuthToken": self._token_provider.get_token()}

    async def _get_auth_headers_async(self) -> dict[str, str]:
        if not self._token_provider:
            return {}
        return {"AuthToken": await self._token_provider.get_token_async()}

    def _should_retry(self, method: str, status_code: int | None = None) -> bool:
        if method.upper() not in self.SAFE_RETRY_METHODS:
            return False
        return status_code is None or status_code in self.RETRYABLE_STATUS_CODES

    def _compute_backoff(self, attempt: int, retry_after: str | None = None) -> float:
        if retry_after:
            try:
                value = float(retry_after)
            except ValueError:
                value = -1.0
            if value >= 0:
                return value

        delay = min(self._base_retry_delay * (2 ** (attempt - 1)), self._max_retry_delay)
        jitter = random.uniform(0, delay * 0.25)
        return delay + jitter

    def _parse_response(self, response: httpx.Response) -> Any:
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            return response.json()
        if "application/xml" in content_type or "text/xml" in content_type:
            return response.text
        if "text/" in content_type:
            return response.text
        return response.content

    def _raise_for_response(self, response: httpx.Response, method: str) -> None:
        if not response.is_error:
            return

        try:
            response_text = response.text
        except Exception:
            response_text = None

        try:
            response_json = response.json()
        except Exception:
            response_json = None

        exc_cls = RetryableAPIError if self._should_retry(method, response.status_code) else NonRetryableAPIError
        raise exc_cls(
            f"HTTP {response.status_code} returned from {response.request.url}",
            status_code=response.status_code,
            url=str(response.request.url),
            response_text=response_text,
            response_json=response_json,
        )

    def request(
        self,
        method: str,
        *,
        endpoint: str = "",
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        allow_retry: bool | None = None,
    ) -> Any:
        self._ensure_open_sync()
        method = method.upper()
        url = self._build_url(endpoint=endpoint)
        retry_enabled = self._should_retry(method) if allow_retry is None else allow_retry

        for attempt in range(1, self._max_retries + 1):
            merged_headers = dict(headers or {})
            merged_headers.update(self._get_auth_headers())

            try:
                response = self._sync_client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    data=data,
                    headers=merged_headers,
                )

                if response.status_code == 401 and self._token_provider:
                    self._token_provider.invalidate()
                    if retry_enabled and attempt < self._max_retries:
                        time.sleep(self._compute_backoff(attempt, response.headers.get("Retry-After")))
                        continue

                self._raise_for_response(response, method)
                return self._parse_response(response)
            except RetryableAPIError:
                if not retry_enabled or attempt >= self._max_retries:
                    raise
                time.sleep(self._compute_backoff(attempt))
            except httpx.TimeoutException as exc:
                if not retry_enabled or attempt >= self._max_retries:
                    raise RequestTimeoutError(
                        f"Request timed out after {attempt} attempt(s): {exc}",
                        url=url,
                    ) from exc
                time.sleep(self._compute_backoff(attempt))
            except httpx.NetworkError as exc:
                if not retry_enabled or attempt >= self._max_retries:
                    raise TransportError(
                        f"Network error after {attempt} attempt(s): {exc}",
                        url=url,
                    ) from exc
                time.sleep(self._compute_backoff(attempt))
            except httpx.HTTPError as exc:
                raise NonRetryableAPIError(f"HTTP client error: {exc}", url=url) from exc

        raise NonRetryableAPIError(f"Exhausted retries for {method} {url}", url=url)

    async def request_async(
        self,
        method: str,
        *,
        endpoint: str = "",
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        allow_retry: bool | None = None,
    ) -> Any:
        self._ensure_open_async()
        method = method.upper()
        url = self._build_url(endpoint=endpoint)
        retry_enabled = self._should_retry(method) if allow_retry is None else allow_retry

        async with self._get_semaphore():
            for attempt in range(1, self._max_retries + 1):
                merged_headers = dict(headers or {})
                merged_headers.update(await self._get_auth_headers_async())

                try:
                    response = await self._async_client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json,
                        data=data,
                        headers=merged_headers,
                    )

                    if response.status_code == 401 and self._token_provider:
                        self._token_provider.invalidate()
                        if retry_enabled and attempt < self._max_retries:
                            await asyncio.sleep(
                                self._compute_backoff(attempt, response.headers.get("Retry-After"))
                            )
                            continue

                    self._raise_for_response(response, method)
                    return self._parse_response(response)
                except RetryableAPIError:
                    if not retry_enabled or attempt >= self._max_retries:
                        raise
                    await asyncio.sleep(self._compute_backoff(attempt))
                except httpx.TimeoutException as exc:
                    if not retry_enabled or attempt >= self._max_retries:
                        raise RequestTimeoutError(
                            f"Async request timed out after {attempt} attempt(s): {exc}",
                            url=url,
                        ) from exc
                    await asyncio.sleep(self._compute_backoff(attempt))
                except httpx.NetworkError as exc:
                    if not retry_enabled or attempt >= self._max_retries:
                        raise TransportError(
                            f"Network error after {attempt} attempt(s): {exc}",
                            url=url,
                        ) from exc
                    await asyncio.sleep(self._compute_backoff(attempt))
                except httpx.HTTPError as exc:
                    raise NonRetryableAPIError(f"HTTP client error: {exc}", url=url) from exc

        raise NonRetryableAPIError(f"Exhausted retries for {method} {url}", url=url)

    def _get(self, *, endpoint: str = "", params: Mapping[str, Any] | None = None) -> Any:
        return self.request("GET", endpoint=endpoint, params=params)

    def _post(
        self,
        *,
        endpoint: str = "",
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        allow_retry: bool | None = None,
    ) -> Any:
        return self.request(
            "POST",
            endpoint=endpoint,
            params=params,
            json=json,
            data=data,
            allow_retry=allow_retry,
        )

    def _put(
        self,
        *,
        endpoint: str = "",
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        allow_retry: bool | None = None,
    ) -> Any:
        return self.request(
            "PUT",
            endpoint=endpoint,
            params=params,
            json=json,
            data=data,
            allow_retry=allow_retry,
        )

    async def _get_async(self, *, endpoint: str = "", params: Mapping[str, Any] | None = None) -> Any:
        return await self.request_async("GET", endpoint=endpoint, params=params)

    async def _post_async(
        self,
        *,
        endpoint: str = "",
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        allow_retry: bool | None = None,
    ) -> Any:
        return await self.request_async(
            "POST",
            endpoint=endpoint,
            params=params,
            json=json,
            data=data,
            allow_retry=allow_retry,
        )

    async def _put_async(
        self,
        *,
        endpoint: str = "",
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        allow_retry: bool | None = None,
    ) -> Any:
        return await self.request_async(
            "PUT",
            endpoint=endpoint,
            params=params,
            json=json,
            data=data,
            allow_retry=allow_retry,
        )

    @staticmethod
    def require_field(payload: Mapping[str, Any], field_name: str) -> Any:
        value = payload.get(field_name)
        if value is None:
            raise UnexpectedResponseError(f"Response payload is missing required field '{field_name}'.")
        return value

    @staticmethod
    def require_str_field(payload: Mapping[str, Any], field_name: str) -> str:
        value = BaseAPI.require_field(payload, field_name)
        if not isinstance(value, str):
            raise UnexpectedResponseError(
                f"Field '{field_name}' must be str, got {type(value).__name__}."
            )
        return value

    @staticmethod
    def require_list_field(payload: Mapping[str, Any], field_name: str) -> list[Any]:
        value = BaseAPI.require_field(payload, field_name)
        if not isinstance(value, list):
            raise UnexpectedResponseError(
                f"Field '{field_name}' must be list, got {type(value).__name__}."
            )
        return value

    @staticmethod
    def ensure_unique_keys(keys: list[str]) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for key in keys:
            if key in seen:
                duplicates.add(key)
            seen.add(key)
        if duplicates:
            raise UnexpectedResponseError(f"Duplicate batch keys detected: {sorted(duplicates)}")

    @staticmethod
    async def gather_dict(
        tasks_by_key: Mapping[str, asyncio.Future],
        *,
        fail_on_any_error: bool = True,
    ) -> dict[str, Any]:
        output, failures = await BaseAPI.gather_dict_detailed(tasks_by_key)

        if failures and fail_on_any_error:
            raise BatchRequestError(
                f"{len(failures)} task(s) failed out of {len(tasks_by_key)}.",
                failures=failures,
            )
        return output

    @staticmethod
    async def gather_dict_detailed(
        tasks_by_key: Mapping[str, asyncio.Future],
    ) -> tuple[dict[str, Any], dict[str, Exception]]:
        BaseAPI.ensure_unique_keys(list(tasks_by_key.keys()))
        results = await asyncio.gather(*tasks_by_key.values(), return_exceptions=True)

        output: dict[str, Any] = {}
        failures: dict[str, Exception] = {}
        for key, result in zip(tasks_by_key.keys(), results):
            if isinstance(result, Exception):
                failures[key] = result
            else:
                output[key] = result

        return output, failures

    @staticmethod
    def encode_path(value: str) -> str:
        return quote(value, safe="")

    @property
    def base_url(self) -> str:
        return self._base_url
