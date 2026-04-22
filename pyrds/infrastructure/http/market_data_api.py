from __future__ import annotations

import asyncio
from typing import Any

from pyrds.infrastructure.config.settings import ApiClientSettings
from pyrds.infrastructure.http.base_api import BaseAPI


class MarketDataApi(BaseAPI):
    def __init__(self, settings: ApiClientSettings, logger: Any | None = None) -> None:
        super().__init__(logger=logger, settings=settings, semaphore=20)

    def get_version(self, endpoint: str = "GetVersion") -> str:
        response = self._get(endpoint=endpoint)
        return self.require_str_field(response, "version")

    def create_set(
        self,
        endpoint: str = "marketdata-sets",
        is_public: bool = False,
        params: dict[str, Any] | None = None,
    ) -> str:
        response = self._post(
            endpoint=endpoint,
            json={"is_public": is_public},
            params=params,
            allow_retry=False,
        )
        return self.require_str_field(response, "marketdata_set_id")

    def add_qml(
        self,
        set_id: str,
        market_data_id: str,
        market_data_qml: str,
        endpoint: str = "marketdata-sets",
        params: dict[str, Any] | None = None,
    ) -> Any:
        endpoint = f"{endpoint}/{self.encode_path(set_id)}/marketdata/{self.encode_path(market_data_id)}"
        return self._put(
            endpoint=endpoint,
            json={"qml": market_data_qml},
            params=params,
            allow_retry=False,
        )

    def get_mkt_data_keys(
        self,
        set_id: str,
        endpoint: str = "marketdata-sets",
        params: dict[str, Any] | None = None,
    ) -> list[Any]:
        response = self._get(endpoint=f"{endpoint}/{self.encode_path(set_id)}/marketdata", params=params)
        return self.require_list_field(response, "marketdata_key")

    async def get_mkt_data_keys_async(
        self,
        set_id: str,
        endpoint: str = "marketdata-sets",
        params: dict[str, Any] | None = None,
    ) -> list[Any]:
        response = await self._get_async(endpoint=f"{endpoint}/{self.encode_path(set_id)}/marketdata", params=params)
        return self.require_list_field(response, "marketdata_key")

    def get_mkt_data_content(
        self,
        set_id: str,
        key: str,
        endpoint: str = "marketdata-sets",
        params: dict[str, Any] | None = None,
    ) -> str:
        response = self._get(
            endpoint=f"{endpoint}/{self.encode_path(set_id)}/marketdata/{self.encode_path(key)}",
            params=params,
        )
        return self.require_str_field(response, "qml")

    async def get_mkt_data_content_async(
        self,
        set_id: str,
        key: str,
        endpoint: str = "marketdata-sets",
        params: dict[str, Any] | None = None,
    ) -> str:
        response = await self._get_async(
            endpoint=f"{endpoint}/{self.encode_path(set_id)}/marketdata/{self.encode_path(key)}",
            params=params,
        )
        return self.require_str_field(response, "qml")

    def get_ot_mkt_data_set_id(
        self,
        endpoint: str = "MarketData/GetMarketDataSetId",
        **params: Any,
    ) -> str:
        response = self._post(endpoint=endpoint, json=params, allow_retry=False)
        return self.require_str_field(response, "setid")

    async def get_ot_mkt_data_qmls_async(
        self,
        set_id: str,
        endpoint: str = "marketdata-sets",
        params: dict[str, Any] | None = None,
        *,
        fail_on_any_error: bool = True,
    ) -> dict[str, str]:
        keys = await self.get_mkt_data_keys_async(set_id=set_id, endpoint=endpoint, params=params)
        tasks_by_key: dict[str, asyncio.Future[str]] = {}

        for key in keys:
            tasks_by_key[key] = asyncio.create_task(
                self._get_single_qml(
                    f"{endpoint}/{self.encode_path(set_id)}/marketdata/{self.encode_path(key)}",
                    params=params,
                )
            )

        return await self.gather_dict(tasks_by_key, fail_on_any_error=fail_on_any_error)

    async def _get_single_qml(self, endpoint: str, params: dict[str, Any] | None = None) -> str:
        response = await self._get_async(endpoint=endpoint, params=params)
        return self.require_str_field(response, "qml")
