from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator

from pyrds.domain.ps_request import PsRequest


class SimplePricingInput(BaseModel):
    request_id: str
    ps_request: PsRequest | dict[str, Any] = Field(
        validation_alias=AliasChoices("ps_request", "price_payload")
    )
    market_data_set_id: str | None = None
    trade_set_id: str | None = None
    market_data: dict[str, str] = Field(default_factory=dict)
    trade_id: str | None = None
    product_qml: str | None = None
    pricing_parameters_qml: str | None = None

    @model_validator(mode="after")
    def validate_trade_inputs(self) -> "SimplePricingInput":
        if self.trade_set_id:
            return self
        if self.product_qml and self.pricing_parameters_qml and self.trade_id:
            return self
        raise ValueError(
            "Provide either trade_set_id or trade_id + product_qml + pricing_parameters_qml."
        )


class FullQmlPricingInput(BaseModel):
    runner: str
    instruction_set_qml: str
    request_qml: str
    request_set_id: str | None = None


class BatchPricingInput(BaseModel):
    requests: list[PsRequest | dict[str, Any]]
