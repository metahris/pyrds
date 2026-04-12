from __future__ import annotations

from typing import Any

from pyrds.application.dto.pricing import BatchPricingInput, FullQmlPricingInput, SimplePricingInput
from pyrds.application.runners.full_qml_pricing_runner import FullQmlPricingRunner
from pyrds.application.runners.simple_pricing_runner import SimplePricingRunner
from pyrds.application.services.payload_mapper import model_to_payload
from pyrds.domain.models import PricingExecutionResult
from pyrds.infrastructure.config.settings import Settings
from pyrds.infrastructure.http.market_data_api import MarketDataApi
from pyrds.infrastructure.http.ps_api import PsApi
from pyrds.infrastructure.http.trades_api import TradesApi


class PyrdsClient:
    def __init__(self, settings: Settings | None = None, logger: Any | None = None) -> None:
        self.settings = settings or Settings.load()
        self.logger = logger
        self.market_data_api = MarketDataApi(self.settings.market_data_api, logger=logger)
        self.trades_api = TradesApi(self.settings.trades_api, logger=logger)
        self.pricing_api = PsApi(self.settings.pricing_api, logger=logger)

        self.simple_pricing_runner = SimplePricingRunner(
            market_data_port=self.market_data_api,
            trades_port=self.trades_api,
            pricing_port=self.pricing_api,
        )
        self.full_qml_pricing_runner = FullQmlPricingRunner(pricing_port=self.pricing_api)

    def price_simple(self, data: SimplePricingInput) -> PricingExecutionResult:
        return self.simple_pricing_runner.run(data)

    def price_full_qml(self, data: FullQmlPricingInput) -> PricingExecutionResult:
        return self.full_qml_pricing_runner.run(data)

    async def price_batch(self, data: BatchPricingInput) -> PricingExecutionResult:
        normalized_requests = [model_to_payload(request) for request in data.requests]
        response = await self.pricing_api.price_async(normalized_requests, fail_on_any_error=False)
        return PricingExecutionResult(
            workflow="batch-pricing",
            payload={"size": len(data.requests)},
            raw_response=response,
        )

    def create_generic_runner(
        self,
        *,
        files_path: Any,
        qml_handler: Any,
        request_set_tags: set[str] | list[str] | None = None,
    ) -> Any:
        from pyrds.application.runners.generic_runner import GenericRunner

        return GenericRunner(
            logger=self.logger,
            files_path=files_path,
            qml_handler=qml_handler,
            ps_api=self.pricing_api,
            market_api=self.market_data_api,
            trades_api=self.trades_api,
            request_set_tags=request_set_tags,
        )

    def create_hybrid_runner(
        self,
        *,
        files_path: Any,
        qml_handler: Any,
        request_set_tags: set[str] | list[str] | None = None,
    ) -> Any:
        from pyrds.application.runners.hybrid_runner import HybridRunner

        return HybridRunner(
            logger=self.logger,
            files_path=files_path,
            qml_handler=qml_handler,
            ps_api=self.pricing_api,
            market_api=self.market_data_api,
            trades_api=self.trades_api,
            request_set_tags=request_set_tags,
        )

    def create_backtester(
        self,
        *,
        files_path: Any,
        qml_handler: Any,
        request_set_tags: set[str] | list[str] | None = None,
    ) -> Any:
        from pyrds.application.runners.backtester import Backtester

        return Backtester(
            logger=self.logger,
            files_path=files_path,
            qml_handler=qml_handler,
            ps_api=self.pricing_api,
            market_api=self.market_data_api,
            trades_api=self.trades_api,
            request_set_tags=request_set_tags,
        )

    def create_override_qml_runner(
        self,
        *,
        files_path: Any,
        qml_handler: Any,
        request_set_tags: set[str] | list[str] | None = None,
    ) -> Any:
        from pyrds.application.runners.override_qml_runner import OverrideQmlRunner

        return OverrideQmlRunner(
            logger=self.logger,
            files_path=files_path,
            qml_handler=qml_handler,
            ps_api=self.pricing_api,
            market_api=self.market_data_api,
            trades_api=self.trades_api,
            request_set_tags=request_set_tags,
        )

    def create_override_qmls_runner(
        self,
        *,
        files_path: Any,
        qml_handler: Any,
        request_set_tags: set[str] | list[str] | None = None,
    ) -> Any:
        from pyrds.application.runners.override_qmls_runner import OverrideQmlsRunner

        return OverrideQmlsRunner(
            logger=self.logger,
            files_path=files_path,
            qml_handler=qml_handler,
            ps_api=self.pricing_api,
            market_api=self.market_data_api,
            trades_api=self.trades_api,
            request_set_tags=request_set_tags,
        )

    def create_stress_runner(
        self,
        *,
        files_path: Any,
        qml_handler: Any,
        request_set_tags: set[str] | list[str] | None = None,
    ) -> Any:
        from pyrds.application.runners.stress_runner import StressRunner

        return StressRunner(
            logger=self.logger,
            files_path=files_path,
            qml_handler=qml_handler,
            ps_api=self.pricing_api,
            market_api=self.market_data_api,
            trades_api=self.trades_api,
            request_set_tags=request_set_tags,
        )

    def create_qlib_req_validator(
        self,
        *,
        files_path: Any,
        qml_handler: Any,
        request_set_tags: set[str] | list[str] | None = None,
    ) -> Any:
        from pyrds.application.runners.qlib_req_validator import QlibReqValidator

        return QlibReqValidator(
            logger=self.logger,
            files_path=files_path,
            qml_handler=qml_handler,
            ps_api=self.pricing_api,
            market_api=self.market_data_api,
            trades_api=self.trades_api,
            request_set_tags=request_set_tags,
        )

    def close(self) -> None:
        self.market_data_api.close()
        self.trades_api.close()
        self.pricing_api.close()

    async def aclose(self) -> None:
        await self.market_data_api.aclose()
        await self.trades_api.aclose()
        await self.pricing_api.aclose()

    def __enter__(self) -> "PyrdsClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    async def __aenter__(self) -> "PyrdsClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()
