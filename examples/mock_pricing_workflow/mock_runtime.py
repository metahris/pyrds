from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


class MockLogger:
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        print(msg % args if args else msg)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        print(msg % args if args else msg)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        print(msg % args if args else msg)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        print(msg % args if args else msg)


@dataclass(slots=True)
class MockFilesPath:
    working_dir: str

    @property
    def inputs(self) -> str:
        return str(Path(self.working_dir) / "inputs")

    @property
    def data(self) -> str:
        return str(Path(self.inputs) / "data")

    @property
    def trade(self) -> str:
        return str(Path(self.inputs) / "trade")

    @property
    def results(self) -> str:
        path = Path(self.working_dir) / "results"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def qml_updater(self) -> str:
        path = Path(self.working_dir) / "qml_updater"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    @property
    def backtest(self) -> str:
        path = Path(self.working_dir) / "backtest"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)


class MockQmlHandler:
    def load_qml(self, file_path: str) -> str:
        return Path(file_path).read_text(encoding="utf-8")

    def load_qmls(self, folder_path: str) -> dict[str, dict[str, str]]:
        output: dict[str, dict[str, str]] = {}
        for file_path in sorted(Path(folder_path).glob("*.xml")):
            raw_data = file_path.read_text(encoding="utf-8")
            output[file_path.stem] = {
                "data_type": self._detect_data_type(raw_data, file_path.stem),
                "raw_data": raw_data,
            }
        return output

    def dump_qml(self, *, dump_path: str, data: str | dict[str, str]) -> None:
        path = Path(dump_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, dict):
            content = "\n".join(
                f"<!-- {key} -->\n{value}"
                for key, value in data.items()
            )
        else:
            content = data
        path.write_text(content, encoding="utf-8")

    def dump_qml_concurrent(self, *, output_dir: str, data: dict[str, str]) -> None:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        for key, value in data.items():
            self.dump_qml(dump_path=str(path / f"{key}.xml"), data=value)

    def verify_instruction_set_qml(self, *, instruction_set_qml: str, ps_request: Any | None = None) -> None:
        if instruction_set_qml and "<InstructionSet" not in instruction_set_qml:
            raise ValueError("Mock instruction set qml is invalid.")

    def verify_request_qml(self, *, request_qml: str) -> str:
        if "<Request" not in request_qml:
            raise ValueError("Mock request qml is invalid.")
        return request_qml

    def get_product_name(self, qml: str | None) -> str | None:
        if not qml:
            return None
        return self._find_text(qml, "ProductName") or "MockProduct"

    def parse_result_price(self, qml: str | None = None, result_qml: str | None = None) -> dict[str, Any]:
        text = qml or result_qml or ""
        total = self._find_text(text, "Total") or "0"
        currency = self._find_text(text, "Currency") or "EUR"
        return {
            "price": {
                "PRICE": {
                    "total": {
                        "price": total,
                        "currency": currency,
                    }
                }
            }
        }

    def get_pricing_duration(self, *, qml: str) -> float:
        value = self._find_text(qml, "DurationMs") or "0"
        return float(value)

    def get_valdate_from_price_instruction(self, instruction_set_qml: str) -> str:
        return self._find_text(instruction_set_qml, "ValuationDate") or "2026-04-12"

    def update_request_with_mult_add_shift_scenarios(self, *, request_qml: str, stresses_request: Any) -> str:
        return request_qml.replace("</Request>", "<StressScenario>mock</StressScenario></Request>")

    def update_block_in_qml(self, *, qml: str, block: str, data_id: str) -> str:
        return qml.replace("</", f"<MockOverride dataId=\"{data_id}\">{block}</MockOverride></", 1)

    def override_in_xpath(self, *, qml: str, overrides: list[Any]) -> str:
        return qml

    def get_fx_tree(self, *, qml: str) -> dict[str, Any]:
        return {"mock": True, "source": qml[:32]}

    @staticmethod
    def _detect_data_type(raw_data: str, fallback: str) -> str:
        try:
            return ET.fromstring(raw_data).tag.lower()
        except Exception:
            lower = fallback.lower()
            if "pricing" in lower:
                return "pricingparams"
            if "product" in lower:
                return "product"
            if "request" in lower:
                return "request"
            if "instruction" in lower:
                return "instructionset"
            return "marketdata"

    @staticmethod
    def _find_text(xml_text: str, tag: str) -> str | None:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", xml_text, flags=re.DOTALL)
        return match.group(1).strip() if match else None


class MockMarketDataApi:
    def __init__(self) -> None:
        self._counter = 0
        self.sets: dict[str, dict[str, str]] = {}
        self.ot_set_id = "OT-MKT-001"
        self.sets[self.ot_set_id] = {
            "OT|BASE": "<MarketData><Name>OT|BASE</Name><Curve>OT</Curve></MarketData>"
        }

    def create_set(
        self,
        endpoint: str = "marketdata-sets",
        is_public: bool = False,
        params: dict[str, Any] | None = None,
    ) -> str:
        self._counter += 1
        set_id = f"MKT-{self._counter:03d}"
        self.sets[set_id] = {}
        return set_id

    def add_qml(
        self,
        set_id: str,
        market_data_id: str,
        market_data_qml: str,
        endpoint: str = "marketdata-sets",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.sets.setdefault(set_id, {})[market_data_id] = market_data_qml
        return {"setId": set_id, "marketDataId": market_data_id}

    def get_mkt_data_keys(self, set_id: str, endpoint: str = "marketdata-sets") -> list[str]:
        return list(self.sets.get(set_id, {}).keys())

    async def get_mkt_data_keys_async(self, set_id: str, endpoint: str = "marketdata-sets") -> list[str]:
        return self.get_mkt_data_keys(set_id=set_id, endpoint=endpoint)

    def get_mkt_data_content(self, set_id: str, key: str, endpoint: str = "marketdata-sets") -> str:
        return self.sets[set_id][key]

    async def get_mkt_data_content_async(self, set_id: str, key: str, endpoint: str = "marketdata-sets") -> str:
        return self.get_mkt_data_content(set_id=set_id, key=key, endpoint=endpoint)

    def get_ot_mkt_data_set_id(self, endpoint: str = "MarketData/GetMarketDataSetId", **params: Any) -> str:
        return self.ot_set_id

    async def get_ot_mkt_data_qmls_async(
        self,
        set_id: str,
        endpoint: str = "marketdata-sets",
        *,
        fail_on_any_error: bool = True,
    ) -> dict[str, str]:
        await asyncio.sleep(0)
        return dict(self.sets.get(set_id, {}))


class MockTradesApi:
    def __init__(self) -> None:
        self._counter = 0
        self.sets: dict[str, dict[str, dict[str, str]]] = {}

    def create_set(
        self,
        endpoint: str = "trade-sets",
        params: dict[str, Any] | None = None,
    ) -> str:
        self._counter += 1
        set_id = f"TRD-{self._counter:03d}"
        self.sets[set_id] = {}
        return set_id

    def add_qml(
        self,
        set_id: str,
        trade_id: str,
        product_qml: str,
        pricing_parameters_qml: str,
        endpoint: str = "trade-sets",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.sets.setdefault(set_id, {})[trade_id] = {
            "qml_product": product_qml,
            "qml_pricing_params": pricing_parameters_qml,
        }
        return {"setId": set_id, "tradeId": trade_id}

    def get_trades_in_set(self, set_id: str, endpoint: str = "trade-sets") -> list[str]:
        return list(self.sets.get(set_id, {}).keys())

    async def get_trades_in_set_async(self, set_id: str, endpoint: str = "trade-sets") -> list[str]:
        return self.get_trades_in_set(set_id=set_id, endpoint=endpoint)

    def get_trade_content(self, set_id: str, trade_id: str, endpoint: str = "trade-sets") -> dict[str, str]:
        return dict(self.sets[set_id][trade_id])

    async def get_trade_content_async(
        self,
        set_id: str,
        trade_id: str,
        endpoint: str = "trade-sets",
    ) -> dict[str, str]:
        return self.get_trade_content(set_id=set_id, trade_id=trade_id, endpoint=endpoint)

    async def get_specific_trade_content_async(
        self,
        set_id: str,
        trade_ids: list[str],
        endpoint: str = "trade-sets",
        *,
        fail_on_any_error: bool = True,
    ) -> dict[str, dict[str, str]]:
        return {
            trade_id: self.get_trade_content(set_id=set_id, trade_id=trade_id, endpoint=endpoint)
            for trade_id in trade_ids
        }


class MockPsApi:
    def __init__(self) -> None:
        self._counter = 0
        self.request_sets: dict[str, dict[str, str]] = {}

    def create_set(self, qml_runner: str, endpoint: str = "requestDataService/dataset/id") -> str:
        self._counter += 1
        set_id = f"REQSET-{self._counter:03d}"
        self.request_sets[set_id] = {"qmlRunner": qml_runner}
        return set_id

    def add_qml(
        self,
        set_id: str,
        instruction_set_qml: str,
        request_qml: str,
        qml_runner: str,
        endpoint: str = "requestDataService/dataset/item",
    ) -> str:
        self.request_sets[set_id] = {
            "qmlRunner": qml_runner,
            "instructionSet": instruction_set_qml,
            "request": request_qml,
        }
        return set_id

    def price(self, body: dict[str, Any], endpoint: str = "price") -> dict[str, Any]:
        request_id = str(body.get("requestId") or f"REQ-{self._counter + 1:03d}")
        trade_set_id = str(body.get("tradeSetId") or "TRD-OT")
        trade_id = str(body.get("tradeId") or "MOCK-TRADE-001")
        request_set_id = body.get("requestDataSetId")
        market_data_set_ids = self._market_data_set_ids(body)
        result_qml = self._result_qml(request_id=request_id, trade_id=trade_id)
        return {
            "responses": [
                {
                    "psRequestKey": request_id,
                    "requestId": request_id,
                    "tradeId": trade_id,
                    "tradeSetId": trade_set_id,
                    "requestDataSetId": request_set_id,
                    "marketDataSetIds": market_data_set_ids,
                    "rawResults": [result_qml],
                    "errors": [],
                }
            ]
        }

    async def price_async(
        self,
        priceable: list[dict[str, Any]],
        endpoint: str = "price",
        *,
        fail_on_any_error: bool = False,
    ) -> dict[str, dict[str, Any]]:
        await asyncio.sleep(0)
        output: dict[str, dict[str, Any]] = {}
        for index, body in enumerate(priceable):
            key = str(body.get("requestId") or index)
            output[key] = self.price(body=body, endpoint=endpoint)
        return output

    @staticmethod
    def _market_data_set_ids(body: dict[str, Any]) -> list[str]:
        values = body.get("marketDataSetIds")
        if isinstance(values, list):
            return [str(value) for value in values]
        value = body.get("marketDataSetId")
        if value:
            return [str(value)]
        return ["OT-MKT-001"]

    @staticmethod
    def _result_qml(*, request_id: str, trade_id: str) -> str:
        return (
            "<PricingResult>"
            f"<ProductName>{trade_id}</ProductName>"
            "<Currency>EUR</Currency>"
            "<Total>123.45</Total>"
            "<DurationMs>17.5</DurationMs>"
            f"<RequestId>{request_id}</RequestId>"
            "</PricingResult>"
        )
