from __future__ import annotations

from typing import Any, Protocol


class PricingPort(Protocol):
    def create_set(self, qml_runner: str) -> str:
        ...

    def add_qml(
        self,
        set_id: str,
        instruction_set_qml: str,
        request_qml: str,
        qml_runner: str,
    ) -> str:
        ...

    def price(self, body: dict[str, Any]) -> dict[str, Any]:
        ...

    async def price_async(
        self,
        priceable: list[dict[str, Any]],
        *,
        fail_on_any_error: bool = False,
    ) -> dict[str, Any]:
        ...
