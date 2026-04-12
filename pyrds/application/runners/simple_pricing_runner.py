from __future__ import annotations

from pyrds.application.dto.pricing import SimplePricingInput
from pyrds.application.ports.market_data import MarketDataPort
from pyrds.application.ports.pricing import PricingPort
from pyrds.application.ports.trades import TradesPort
from pyrds.application.services.payload_mapper import model_to_payload
from pyrds.domain.models import PricingExecutionResult
from pyrds.domain.models import PricingWorkflowContext


class SimplePricingRunner:
    def __init__(
        self,
        *,
        market_data_port: MarketDataPort,
        trades_port: TradesPort,
        pricing_port: PricingPort,
    ) -> None:
        self._market_data_port = market_data_port
        self._trades_port = trades_port
        self._pricing_port = pricing_port

    def run(self, data: SimplePricingInput) -> PricingExecutionResult:
        market_data_set_id = data.market_data_set_id
        if not market_data_set_id and data.market_data:
            market_data_set_id = self._market_data_port.create_set(is_public=False)
            for market_data_id, qml in data.market_data.items():
                self._market_data_port.add_qml(
                    set_id=market_data_set_id,
                    market_data_id=market_data_id,
                    market_data_qml=qml,
                )

        trade_set_id = data.trade_set_id
        if not trade_set_id:
            trade_set_id = self._trades_port.create_set()
            self._trades_port.add_qml(
                set_id=trade_set_id,
                trade_id=data.trade_id or data.request_id,
                product_qml=data.product_qml or "",
                pricing_parameters_qml=data.pricing_parameters_qml or "",
            )

        payload = model_to_payload(data.ps_request)
        payload.setdefault("requestId", data.request_id)
        if market_data_set_id:
            payload.setdefault("marketDataSetIds", [market_data_set_id])
        payload.setdefault("tradeSetId", trade_set_id)

        response = self._pricing_port.price(payload)
        return PricingExecutionResult(
            workflow="simple-pricing",
            context=PricingWorkflowContext(
                market_data_set_id=market_data_set_id,
                trade_set_id=trade_set_id,
            ),
            payload=payload,
            raw_response=response,
        )
