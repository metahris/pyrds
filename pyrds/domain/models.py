from __future__ import annotations

import json
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CustomBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="allow",
        populate_by_name=True,
        from_attributes=True,
    )

    @classmethod
    def model_validate_json(
        cls,
        json_data: str | bytes | bytearray | dict[str, Any] | list[Any],
        *,
        strict: bool | None = None,
        context: Any | None = None,
    ) -> Self:
        if isinstance(json_data, (dict, list)):
            json_data = json.dumps(json_data)
        return super().model_validate_json(json_data, strict=strict, context=context)


class PricingWorkflowContext(CustomBaseModel):
    market_data_set_id: str | None = None
    trade_set_id: str | None = None
    request_set_id: str | None = None


class PricingExecutionResult(CustomBaseModel):
    workflow: str
    context: PricingWorkflowContext = Field(default_factory=PricingWorkflowContext)
    payload: dict[str, Any] = Field(default_factory=dict)
    raw_response: dict[str, Any] = Field(default_factory=dict)
