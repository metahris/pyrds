from __future__ import annotations

from typing import Protocol


class MarketDataPort(Protocol):
    def create_set(self, is_public: bool = False) -> str:
        ...

    def add_qml(self, set_id: str, market_data_id: str, market_data_qml: str) -> object:
        ...
