from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field

from pyrds.domain.ps_request import PsRequest


class SimplePricingRequest(BaseModel):
    request_id: str
    ps_request: PsRequest = Field(validation_alias=AliasChoices("ps_request", "price_payload"))
    market_data_set_id: str | None = None
    trade_set_id: str | None = None
    market_data: dict[str, str] = Field(default_factory=dict)
    trade_id: str | None = None
    product_qml: str | None = None
    pricing_parameters_qml: str | None = None


class FullQmlPricingRequest(BaseModel):
    runner: str
    instruction_set_qml: str
    request_qml: str
    request_set_id: str | None = None


class BatchPricingRequest(BaseModel):
    requests: list[PsRequest]


class PricingResponse(BaseModel):
    workflow: str
    context: dict[str, Any]
    payload: dict[str, Any]
    raw_response: dict[str, Any]


class ErrorResponse(BaseModel):
    type: str
    detail: str
    status_code: int
    errors: Any | None = None
