from __future__ import annotations

from typing import Any, Protocol


class TradesPort(Protocol):
    def create_set(self) -> str:
        ...

    def add_qml(
        self,
        set_id: str,
        trade_id: str,
        product_qml: str,
        pricing_parameters_qml: str,
    ) -> Any:
        ...
