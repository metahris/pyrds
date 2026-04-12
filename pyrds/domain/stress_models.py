from __future__ import annotations

from typing import Any

from pydantic import Field

from pyrds.domain.models import CustomBaseModel


class StressField(CustomBaseModel):
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class StressRequest(CustomBaseModel):
    stresses: list[StressField]
    metadata: dict[str, Any] = Field(default_factory=dict)
