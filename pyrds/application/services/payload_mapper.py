from __future__ import annotations

from typing import Any

from pyrds.domain.exceptions import ValidationError


def model_to_payload(model_or_payload: Any) -> dict[str, Any]:
    if isinstance(model_or_payload, dict):
        return dict(model_or_payload)
    if hasattr(model_or_payload, "model_dump"):
        return model_or_payload.model_dump(by_alias=True, exclude_none=True)
    if hasattr(model_or_payload, "dict"):
        return model_or_payload.dict(by_alias=True, exclude_none=True)
    raise ValidationError("Expected a PsRequest-like model or dict payload.")
