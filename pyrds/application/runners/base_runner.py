from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from pyrds.application.services.dump_service import DumpService
from pyrds.application.services.log_context import log_error, log_info
from pyrds.application.services.payload_mapper import model_to_payload
from pyrds.application.services.qml_input_service import QmlInputService
from pyrds.application.services.qml_update_service import QmlUpdateService
from pyrds.application.services.response_parser import ResponseParser
from pyrds.domain.exceptions import (
    APIError,
    BatchRequestError,
    PricingComputationError,
    RequestTimeoutError,
    ResultParsingError,
    SetCreationError,
    TransportError,
    ValidationError,
)
from pyrds.domain.ps_request import PsRequest, UseCache
from pyrds.infrastructure.http.market_data_api import MarketDataApi
from pyrds.infrastructure.http.ps_api import PsApi, clear_null_values
from pyrds.infrastructure.http.trades_api import TradesApi

if TYPE_CHECKING:
    import pandas as pd


class BaseRunner:
    @staticmethod
    def adjust_file_name(file_name: str, qml_type: str) -> str:
        return QmlInputService.adjust_file_name(file_name=file_name, qml_type=qml_type)

    @staticmethod
    def result_file_name(prefix: str = "result", extension: str = "xml") -> str:
        return DumpService.result_file_name(prefix=prefix, extension=extension)

    def __init__(
        self,
        *,
        logger: Any,
        files_path: Any,
        qml_handler: Any,
        ps_api: PsApi,
        market_api: MarketDataApi,
        trades_api: TradesApi,
        request_set_tags: set[str] | list[str] | None = None,
    ) -> None:
        self.logger = logger
        self.qml_handler = qml_handler
        self.files_path = files_path

        self.ps_api = ps_api
        self.market_api = market_api
        self.trades_api = trades_api

        self.request_set_tags = set(request_set_tags or [])

        self.qml_inputs = QmlInputService(
            qml_handler=qml_handler,
            files_path=files_path,
            logger=logger,
        )
        self.response_parser = ResponseParser(qml_handler=qml_handler)
        self.dump_service = DumpService(
            qml_handler=qml_handler,
            files_path=files_path,
            logger=logger,
        )
        self.qml_updater = QmlUpdateService(files_path=files_path, logger=logger)

    @staticmethod
    def require_non_empty_str(value: str | None, name: str) -> str:
        if value is None or not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{name} must be a non-empty string.")
        return value

    @staticmethod
    def require_mapping(value: Any, name: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ValidationError(f"{name} must be a mapping.")
        return value

    @staticmethod
    def require_sequence(value: Any, name: str) -> list[Any]:
        if not isinstance(value, list):
            raise ValidationError(f"{name} must be a list.")
        return value

    @staticmethod
    def ensure_unique(values: Iterable[str], name: str) -> None:
        seen: set[str] = set()
        duplicates: set[str] = set()

        for value in values:
            if value in seen:
                duplicates.add(value)
            seen.add(value)

        if duplicates:
            raise ValidationError(f"Duplicate {name}: {sorted(duplicates)}")

    @staticmethod
    def model_to_payload(model_or_payload: Any) -> dict[str, Any]:
        return model_to_payload(model_or_payload)

    def _compute(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.ps_api.price(body=clear_null_values(body))
        except (APIError, RequestTimeoutError, TransportError):
            raise
        except Exception as exc:
            raise PricingComputationError(f"Synchronous pricing failed: {exc}") from exc

        if not isinstance(response, dict):
            raise PricingComputationError("Pricing response must be a dict.")

        return response

    async def _compute_async(
        self,
        priceable: list[dict[str, Any]],
        *,
        fail_on_any_error: bool = False,
    ) -> dict[str, dict[str, Any]]:
        normalized = [clear_null_values(body) for body in priceable]

        try:
            return await self.ps_api.price_async(
                priceable=normalized,
                fail_on_any_error=fail_on_any_error,
            )
        except (APIError, RequestTimeoutError, TransportError, BatchRequestError):
            raise
        except Exception as exc:
            raise PricingComputationError(f"Asynchronous pricing failed: {exc}") from exc

    def create_full_qml_sets(self, *, qml_runner: str) -> dict[str, str]:
        qml_runner = self.require_non_empty_str(qml_runner, "qml_runner")
        params = {"qmlRunner": qml_runner}

        try:
            market_data_set_id = self.market_api.create_set(params=params)
            trade_set_id = self.trades_api.create_set(params=params)
            request_set_id = self.ps_api.create_set(qml_runner=qml_runner)
        except Exception as exc:
            raise SetCreationError("Failed to create one or more remote sets.") from exc

        log_info(
            self.logger,
            "Full QML sets created",
            qml_runner=qml_runner,
            market_data_set_id=market_data_set_id,
            trade_set_id=trade_set_id,
            request_set_id=request_set_id,
        )

        return {
            "market_data_set_id": market_data_set_id,
            "trade_set_id": trade_set_id,
            "request_set_id": request_set_id,
        }

    def add_market_data_qml(
        self,
        *,
        set_id: str,
        params: dict[str, Any] | None = None,
        mkt_data: Mapping[str, str] | None = None,
        market_data_id: str | None = None,
        market_data_qml: str | None = None,
    ) -> None:
        set_id = self.require_non_empty_str(set_id, "set_id")
        if market_data_id is not None or market_data_qml is not None:
            market_data_id = self.require_non_empty_str(market_data_id, "market_data_id")
            market_data_qml = self.require_non_empty_str(market_data_qml, "market_data_qml")
            log_info(
                self.logger,
                "Adding market data QML to set",
                set_id=set_id,
                market_data_id=market_data_id,
            )
            self.market_api.add_qml(
                set_id=set_id,
                market_data_id=market_data_id,
                market_data_qml=market_data_qml,
                params=params,
            )
            return

        if not mkt_data:
            log_info(self.logger, "No market data qml found", set_id=set_id)
            return

        for market_data_id, market_data_qml in mkt_data.items():
            log_info(
                self.logger,
                "Adding market data QML to set",
                set_id=set_id,
                market_data_id=str(market_data_id),
            )
            self.market_api.add_qml(
                set_id=set_id,
                market_data_id=str(market_data_id),
                market_data_qml=str(market_data_qml),
                params=params,
            )

    def add_trade_qml(
        self,
        *,
        set_id: str,
        trade_id: str,
        product_qml: str,
        pricing_params_qml: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        set_id = self.require_non_empty_str(set_id, "set_id")
        trade_id = self.require_non_empty_str(trade_id, "trade_id")

        log_info(
            self.logger,
            "Adding trade QML to set",
            set_id=set_id,
            trade_id=trade_id,
        )
        self.trades_api.add_qml(
            set_id=set_id,
            trade_id=trade_id,
            product_qml=product_qml,
            pricing_parameters_qml=pricing_params_qml,
            params=params,
        )

    def add_request_qml(
        self,
        *,
        set_id: str,
        instruction_set_qml: str,
        request_qml: str,
        qml_runner: str,
    ) -> None:
        set_id = self.require_non_empty_str(set_id, "set_id")
        qml_runner = self.require_non_empty_str(qml_runner, "qml_runner")

        log_info(
            self.logger,
            "Adding request QML to set",
            set_id=set_id,
            qml_runner=qml_runner,
        )
        self.ps_api.add_qml(
            set_id=set_id,
            instruction_set_qml=instruction_set_qml,
            request_qml=request_qml,
            qml_runner=qml_runner,
        )

    def add_set_ids_to_ps_request(
        self,
        *,
        ps_request: PsRequest,
        market_data_set_id: str | list[str] | None = None,
        trade_set_id: str | None = None,
        request_set_id: str | None = None,
        get_ot_mkt_data: bool = False,
        use_cache_factory: Any | None = None,
    ) -> Any:
        if request_set_id:
            if use_cache_factory is not None:
                ps_request.gridPricerTechnicalDetails.useCache = use_cache_factory(
                    requestDataSetId=request_set_id
                )
            else:
                use_cache = getattr(ps_request.gridPricerTechnicalDetails, "useCache", None)
                if use_cache is None:
                    ps_request.gridPricerTechnicalDetails.useCache = UseCache(
                        requestDataSetId=request_set_id
                    )
                elif isinstance(use_cache, dict):
                    use_cache["requestDataSetId"] = request_set_id
                else:
                    setattr(use_cache, "requestDataSetId", request_set_id)
            ps_request.requestDataSetId = request_set_id

        if trade_set_id:
            ps_request.tradeSetId = trade_set_id

        if market_data_set_id:
            if isinstance(market_data_set_id, str):
                if ps_request.marketDataSetIds:
                    ps_request.marketDataSetIds.append(market_data_set_id)
                else:
                    ps_request.marketDataSetIds = [market_data_set_id]
            elif isinstance(market_data_set_id, list):
                if ps_request.marketDataSetIds:
                    ps_request.marketDataSetIds.extend(market_data_set_id)
                else:
                    ps_request.marketDataSetIds = list(market_data_set_id)
            else:
                raise ValidationError("market_data_set_id must be str or list[str].")

        if get_ot_mkt_data:
            params = {
                "cartographyName": ps_request.gridPricerTechnicalDetails.cartography,
                "date": ps_request.valuationDate,
                "otCluster": ps_request.gridPricerTechnicalDetails.foCluster,
                "lagInDaysForHistoricMarketDatas": ps_request.lagInDaysForBackprice,
                "useCache": True,
            }
            ot_market_data_set_id = self.market_api.get_ot_mkt_data_set_id(**params)
            if ps_request.marketDataSetIds:
                ps_request.marketDataSetIds.append(ot_market_data_set_id)
            else:
                ps_request.marketDataSetIds = [ot_market_data_set_id]

        return ps_request

    def get_raw_data(self, response: dict[str, Any] | list[dict[str, Any]]) -> dict[str, str]:
        try:
            raw_data, errors = self.response_parser.get_raw_data(response)
        except Exception as exc:
            raise ResultParsingError("Failed to extract raw data from pricing response.") from exc

        if errors:
            self.dump_service.dump_errors(errors)

        return raw_data

    def get_mkt_data_set_id_from_response(self, response: dict[str, Any] | list[dict[str, Any]]) -> str:
        return self.response_parser.get_market_data_set_id(response)

    def get_trade_set_id_from_response(self, response: dict[str, Any] | list[dict[str, Any]]) -> str:
        return self.response_parser.get_trade_set_id(response)

    def get_request_set_id_from_response(self, response: dict[str, Any] | list[dict[str, Any]]) -> str:
        return self.response_parser.get_request_set_id(response)

    def get_trade_id_from_response(self, response: dict[str, Any] | list[dict[str, Any]]) -> str:
        return self.response_parser.get_trade_id(response)

    def get_ot_mkt_data_set_id(self, **params: Any) -> str:
        return self.market_api.get_ot_mkt_data_set_id(**params)

    def get_total_from_response(self, value: Mapping[str, Any]) -> float | str:
        return self.response_parser.get_total_from_response(value)

    def get_ccy_from_response(self, value: Mapping[str, Any]) -> str:
        return self.response_parser.get_ccy_from_response(value)

    def get_mkt_data_qmls(self) -> dict[str, str]:
        return self.qml_inputs.get_market_data_qmls(self.request_set_tags)

    def get_pricing_params_qml(self) -> str:
        return self.qml_inputs.get_pricing_params_qml()

    def get_pricing_params_qmls(self) -> str:
        return self.get_pricing_params_qml()

    def get_product_qml(self) -> dict[str, str]:
        return self.qml_inputs.get_product_qml()

    def get_instruction_set_qml(self, **kwargs: Any) -> str:
        return self.qml_inputs.get_instruction_set_qml(
            verify=bool(kwargs.get("verify")),
            ps_request=kwargs.get("ps_request"),
        )

    def get_request_qml(self) -> str:
        return self.qml_inputs.get_request_qml()

    def update_qml_to_latest_version(self, in_path: str, out_path: str) -> None:
        self.qml_updater.update_qml_to_latest_version(in_path, out_path)

    def dump_raw_results(self, raw_data: Mapping[str, str], *, file_name: str | None = None) -> str:
        return self.dump_service.dump_raw_results(raw_data, file_name=file_name)

    async def dump_ot_mkt_data_qmls(self, set_id: str) -> str:
        set_id = self.require_non_empty_str(set_id, "set_id")
        try:
            qmls = await self.market_api.get_ot_mkt_data_qmls_async(set_id=set_id)
        except Exception as exc:
            raise PricingComputationError("Failed to retrieve OT market data qmls.") from exc
        return self.dump_service.dump_ot_market_data(qmls=qmls)

    @staticmethod
    def safe_sub(a: Any, b: Any, absolute: bool = False) -> float:
        try:
            value = a - b
        except TypeError:
            return float("nan")
        return abs(value) if absolute else value

    def get_fx_tree(self, mkt_data_set_id: str, mkt_data_id: str) -> dict[str, Any]:
        try:
            qml = self.market_api.get_mkt_data_content(set_id=mkt_data_set_id, key=mkt_data_id)
            return self.qml_handler.get_fx_tree(qml=qml)
        except Exception as exc:
            raise ResultParsingError("Failed to build FX tree from market data.") from exc

    @staticmethod
    def get_usd_fx_value(df: "pd.DataFrame", fx_spots: dict[str, list[Any]]) -> "pd.DataFrame":
        import pandas as pd

        df_fx = pd.DataFrame(fx_spots)
        fx_dict: dict[tuple[str, str], float] = {}

        for _, row in df_fx.iterrows():
            fx_dict[(row["asset"], row["basis"])] = float(row["value"])
            fx_dict[(row["basis"], row["asset"])] = 1 / float(row["value"])

        def get_usd_value(basis: str) -> float | None:
            if basis == "USD":
                return 1

            direct = ("USD", basis)
            if direct in fx_dict:
                return fx_dict[direct]

            for (asset, intermediate_basis), value in fx_dict.items():
                if (
                    asset == "USD"
                    and (intermediate_basis, basis) in fx_dict
                    and (basis, intermediate_basis) in fx_dict
                ):
                    return value * fx_dict[(basis, intermediate_basis)]

            return None

        df["USD/CCY"] = df["currency"].apply(get_usd_value)
        return df

    async def gather_dict(
        self,
        tasks_by_key: Mapping[str, asyncio.Future],
        *,
        fail_on_any_error: bool = True,
    ) -> dict[str, Any]:
        keys = list(tasks_by_key.keys())
        self.ensure_unique(keys, "task keys")
        results = await asyncio.gather(*tasks_by_key.values(), return_exceptions=True)

        output: dict[str, Any] = {}
        failures: dict[str, Exception] = {}

        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                failures[key] = result
            else:
                output[key] = result

        if failures and fail_on_any_error:
            raise BatchRequestError(
                f"{len(failures)} task(s) failed out of {len(keys)}.",
                failures=failures,
            )

        if failures:
            log_error(self.logger, "Batch async execution had failures", failures=list(failures.keys()))

        return output
