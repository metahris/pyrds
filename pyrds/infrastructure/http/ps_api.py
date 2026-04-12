from __future__ import annotations

import asyncio
from typing import Any

from pyrds.domain.exceptions import UnexpectedResponseError
from pyrds.infrastructure.config.settings import ApiClientSettings
from pyrds.infrastructure.http.base_api import BaseAPI


def clear_null_values(data: Any) -> Any:
    if isinstance(data, dict):
        return {key: clear_null_values(value) for key, value in data.items() if value is not None}
    if isinstance(data, list):
        return [clear_null_values(value) for value in data if value is not None]
    return data


class PsApi(BaseAPI):
    def __init__(self, settings: ApiClientSettings, logger: Any | None = None) -> None:
        super().__init__(logger=logger, settings=settings, semaphore=30)

    def get_version(self, endpoint: str = "GetVersion") -> str:
        response = self._get(endpoint=endpoint)
        return self.require_str_field(response, "version")

    def create_set(self, qml_runner: str, endpoint: str = "requestDataService/dataset/id") -> str:
        response = self._post(endpoint=f"{endpoint}/{qml_runner}", allow_retry=False)
        return self.require_str_field(response, "setId")

    def add_qml(
        self,
        set_id: str,
        instruction_set_qml: str,
        request_qml: str,
        qml_runner: str,
        endpoint: str = "requestDataService/dataset/item",
    ) -> str:
        body = {
            "id": set_id,
            "instructionSet": [instruction_set_qml],
            "request": request_qml,
            "requestId": set_id,
            "subtask": True,
        }
        response = self._put(endpoint=f"{endpoint}/{qml_runner}", json=body, allow_retry=False)
        return self.require_str_field(response, "id")

    def price(self, body: dict[str, Any], endpoint: str = "price") -> dict[str, Any]:
        response = self._post(endpoint=endpoint, json=clear_null_values(body), allow_retry=False)
        if not isinstance(response, dict):
            raise UnexpectedResponseError("Expected dict response for price.")
        return response

    async def price_async(
        self,
        priceable: list[dict[str, Any]],
        endpoint: str = "price",
        *,
        fail_on_any_error: bool = False,
    ) -> dict[str, Any]:
        keys: list[str] = []
        normalized_payloads: list[dict[str, Any]] = []
        for index, body in enumerate(priceable):
            cleaned = clear_null_values(body)
            key = str(cleaned.get("requestId")) if cleaned.get("requestId") is not None else str(index)
            keys.append(key)
            normalized_payloads.append(cleaned)

        self.ensure_unique_keys(keys)
        tasks_by_key: dict[str, asyncio.Future[dict[str, Any]]] = {}
        for key, cleaned in zip(keys, normalized_payloads):
            tasks_by_key[key] = asyncio.create_task(self._price_one_async(cleaned, endpoint))
        return await self.gather_dict(tasks_by_key, fail_on_any_error=fail_on_any_error)

    async def _price_one_async(self, body: dict[str, Any], endpoint: str) -> dict[str, Any]:
        response = await self._post_async(endpoint=endpoint, json=body, allow_retry=False)
        if not isinstance(response, dict):
            raise UnexpectedResponseError("Expected dict response for async price.")
        return response
