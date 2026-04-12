from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from pyrds.domain.exceptions import ResultParsingError


@dataclass(slots=True)
class ParsedComputeItem:
    ps_request_key: str | None
    trade_id: str | None
    trade_name: str | None
    raw_result: str | None
    errors: list[Any]
    raw: dict[str, Any]


class ResponseParser:
    def __init__(self, qml_handler: Any) -> None:
        self.qml_handler = qml_handler

    @staticmethod
    def _pick_first_existing_str(payload: Mapping[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value != "":
                return value
        return None

    def parse_compute_items(self, response: dict[str, Any] | list[dict[str, Any]]) -> list[ParsedComputeItem]:
        if isinstance(response, dict):
            items = response.get("responses")
            if not isinstance(items, list):
                raise ResultParsingError("Pricing response must contain 'responses' list.")
        elif isinstance(response, list):
            items = response
        else:
            raise ResultParsingError(f"Unexpected pricing response type: {type(response).__name__}")

        parsed: list[ParsedComputeItem] = []
        for item in items:
            if not isinstance(item, dict):
                raise ResultParsingError("Each response item must be a dict.")

            raw_results = item.get("rawResults") or []
            if raw_results and not isinstance(raw_results, list):
                raise ResultParsingError("'rawResults' must be a list when present.")

            raw_result = raw_results[0] if raw_results else None
            trade_name = self.qml_handler.get_product_name(raw_result) if raw_result else None
            errors = item.get("errors") or []
            if not isinstance(errors, list):
                raise ResultParsingError("'errors' must be a list when present.")

            parsed.append(
                ParsedComputeItem(
                    ps_request_key=self._pick_first_existing_str(item, "psRequestKey", "requestId", "id"),
                    trade_id=self._pick_first_existing_str(item, "tradeId"),
                    trade_name=trade_name,
                    raw_result=raw_result,
                    errors=errors,
                    raw=item,
                )
            )

        return parsed

    def get_raw_data(self, response: dict[str, Any] | list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, Any]]:
        parsed_items = self.parse_compute_items(response)

        data: dict[str, str] = {}
        errors: dict[str, Any] = {}
        error_index = 0

        for item in parsed_items:
            if item.raw_result:
                base_name = item.trade_name or item.trade_id or f"trade_{error_index}"
                request_key = item.ps_request_key or f"request_{error_index}"
                data[f"{base_name}_{request_key}"] = item.raw_result

            if item.errors:
                request_key = item.ps_request_key or f"request_{error_index}"
                errors[f"{error_index}_{request_key}"] = item.errors[0]
                error_index += 1

        if not data:
            raise ResultParsingError("No raw data found in pricing response.")

        return data, errors

    @staticmethod
    def get_market_data_set_id(response: dict[str, Any] | list[dict[str, Any]]) -> str:
        try:
            if isinstance(response, dict):
                return response["responses"][0]["marketDataSetIds"][0]
            return response[0]["marketDataSetIds"][0]
        except Exception as exc:
            raise ResultParsingError("Could not extract marketDataSetIds[0] from response.") from exc

    @staticmethod
    def get_trade_set_id(response: dict[str, Any] | list[dict[str, Any]]) -> str:
        try:
            if isinstance(response, dict):
                return response["responses"][0]["tradeSetId"]
            return response[0]["tradeSetId"]
        except Exception as exc:
            raise ResultParsingError("Could not extract tradeSetId from response.") from exc

    @staticmethod
    def get_request_set_id(response: dict[str, Any] | list[dict[str, Any]]) -> str:
        try:
            if isinstance(response, dict):
                return response["responses"][0]["requestDataSetId"]
            return response[0]["requestDataSetId"]
        except Exception as exc:
            raise ResultParsingError("Could not extract requestDataSetId from response.") from exc

    @staticmethod
    def get_trade_id(response: dict[str, Any] | list[dict[str, Any]]) -> str:
        try:
            if isinstance(response, dict):
                return response["responses"][0]["tradeId"]
            return response[0]["tradeId"]
        except Exception as exc:
            raise ResultParsingError("Could not extract tradeId from response.") from exc

    @staticmethod
    def get_total_from_response(value: Mapping[str, Any]) -> float | str:
        try:
            return float(value["price"]["PRICE"]["total"]["price"])
        except Exception:
            return "Total not found"

    @staticmethod
    def get_ccy_from_response(value: Mapping[str, Any]) -> str:
        try:
            return value["price"]["PRICE"]["total"]["currency"]
        except Exception:
            return "no currency found"
