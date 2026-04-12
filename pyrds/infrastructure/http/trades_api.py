from __future__ import annotations

import asyncio
from typing import Any

from pyrds.domain.exceptions import UnexpectedResponseError

from pyrds.infrastructure.config.settings import ApiClientSettings
from pyrds.infrastructure.http.base_api import BaseAPI


class TradesApi(BaseAPI):
    def __init__(self, settings: ApiClientSettings, logger: Any | None = None) -> None:
        super().__init__(logger=logger, settings=settings, semaphore=20)

    def get_version(self, endpoint: str = "GetVersion") -> str:
        response = self._get(endpoint=endpoint)
        return self.require_str_field(response, "version")

    def create_set(
        self,
        endpoint: str = "trade-sets",
        params: dict[str, Any] | None = None,
    ) -> str:
        response = self._post(endpoint=endpoint, params=params, allow_retry=False)
        return self.require_str_field(response, "setId")

    def add_qml(
        self,
        set_id: str,
        trade_id: str,
        product_qml: str,
        pricing_parameters_qml: str,
        endpoint: str = "trade-sets",
        params: dict[str, Any] | None = None,
    ) -> Any:
        body = [
            {
                "tradeId": trade_id,
                "productQml": {"text": product_qml},
                "pricingParamsQml": {"text": pricing_parameters_qml},
            }
        ]
        endpoint = f"{endpoint}/{self.encode_path(set_id)}"
        return self._put(endpoint=endpoint, json=body, params=params, allow_retry=False)

    def get_set_content(self, set_id: str, endpoint: str = "trade-sets") -> list[Any]:
        response = self._get(endpoint=f"{endpoint}/{self.encode_path(set_id)}")
        return self.require_list_field(response, "trades")

    def get_trade_content(self, set_id: str, trade_id: str, endpoint: str = "trade-sets") -> dict[str, Any]:
        response = self._get(
            endpoint=f"{endpoint}/{self.encode_path(set_id)}/trades/{self.encode_path(trade_id)}"
        )
        if not isinstance(response, dict):
            raise UnexpectedResponseError("Expected dict response for get_trade_content.")
        return response

    async def get_trade_content_async(
        self,
        set_id: str,
        trade_id: str,
        endpoint: str = "trade-sets",
    ) -> dict[str, Any]:
        response = await self._get_async(
            endpoint=f"{endpoint}/{self.encode_path(set_id)}/trades/{self.encode_path(trade_id)}"
        )
        if not isinstance(response, dict):
            raise UnexpectedResponseError("Expected dict response for get_trade_content_async.")
        return response

    def get_trades_in_set(self, set_id: str, endpoint: str = "trade-sets") -> list[Any]:
        response = self._get(endpoint=f"{endpoint}/{self.encode_path(set_id)}/trades")
        return self.require_list_field(response, "ids")

    async def get_trades_in_set_async(self, set_id: str, endpoint: str = "trade-sets") -> list[Any]:
        response = await self._get_async(endpoint=f"{endpoint}/{self.encode_path(set_id)}/trades")
        return self.require_list_field(response, "ids")

    async def get_specific_trade_content_async(
        self,
        set_id: str,
        trade_ids: list[str],
        endpoint: str = "trade-sets",
        *,
        fail_on_any_error: bool = True,
    ) -> dict[str, dict[str, Any]]:
        self.ensure_unique_keys(trade_ids)
        tasks_by_key: dict[str, asyncio.Future[dict[str, Any]]] = {}
        for trade_id in trade_ids:
            tasks_by_key[trade_id] = asyncio.create_task(
                self.get_trade_content_async(set_id=set_id, trade_id=trade_id, endpoint=endpoint)
            )
        return await self.gather_dict(tasks_by_key, fail_on_any_error=fail_on_any_error)
