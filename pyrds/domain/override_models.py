from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from pyrds.domain.exceptions import OverrideValidationError
from pyrds.domain.models import CustomBaseModel


class OverrideTargetType(StrEnum):
    MARKETDATA = "marketdata"
    PRODUCT = "product"
    PRICINGPARAMS = "pricingparams"
    REQUEST = "request"
    INSTRUCTIONSET = "instructionset"


class OverrideOperation(StrEnum):
    REPLACE_FILE = "replace_file"
    REPLACE_BLOCK = "replace_block"
    REPLACE_BLOCKS = "replace_blocks"
    REPLACE_XPATH = "replace_xpath"
    SET_XPATH_TEXT = "set_xpath_text"


class MatchPolicy(StrEnum):
    EXACTLY_ONE = "exactly_one"
    ONE_OR_MORE = "one_or_more"
    ALL = "all"


class QmlSource(CustomBaseModel):
    inline_xml: str | None = None
    file_name: str | None = None
    file_path: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "QmlSource":
        fields = [self.inline_xml, self.file_name, self.file_path]
        count = sum(1 for value in fields if value)
        if count != 1:
            raise OverrideValidationError(
                "QmlSource requires exactly one of inline_xml, file_name, file_path."
            )
        return self


class QmlOverride(CustomBaseModel):
    name: str
    target_type: OverrideTargetType
    operation: OverrideOperation
    target_id: str | None = None
    apply_to_all: bool = False
    source: QmlSource | None = None
    sources: list[QmlSource] | None = None
    xpath: str | None = None
    value: str | None = None
    match_policy: MatchPolicy = MatchPolicy.EXACTLY_ONE
    allow_duplicate_tags: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_override(self) -> "QmlOverride":
        if self.apply_to_all and self.target_id:
            raise OverrideValidationError(
                f"Override '{self.name}' cannot set both apply_to_all=True and target_id."
            )

        if not self.apply_to_all and not self.target_id and self.target_type in {
            OverrideTargetType.MARKETDATA,
            OverrideTargetType.PRODUCT,
            OverrideTargetType.PRICINGPARAMS,
        }:
            raise OverrideValidationError(
                f"Override '{self.name}' requires target_id or apply_to_all=True."
            )

        if self.operation in {OverrideOperation.REPLACE_FILE, OverrideOperation.REPLACE_BLOCK}:
            if self.source is None:
                raise OverrideValidationError(f"Override '{self.name}' requires source.")
        elif self.operation == OverrideOperation.REPLACE_BLOCKS:
            if not self.sources:
                raise OverrideValidationError(f"Override '{self.name}' requires sources.")
        elif self.operation == OverrideOperation.REPLACE_XPATH:
            if self.source is None or not self.xpath:
                raise OverrideValidationError(
                    f"Override '{self.name}' requires source and xpath."
                )
        elif self.operation == OverrideOperation.SET_XPATH_TEXT:
            if self.value is None or not self.xpath:
                raise OverrideValidationError(
                    f"Override '{self.name}' requires value and xpath."
                )

        return self


class OverrideScenario(CustomBaseModel):
    scenario_id: str
    description: str | None = None
    overrides: list[QmlOverride]

    @model_validator(mode="after")
    def validate_scenario(self) -> "OverrideScenario":
        names = [item.name for item in self.overrides]
        if len(names) != len(set(names)):
            raise OverrideValidationError(
                f"Scenario '{self.scenario_id}' contains duplicate override names."
            )
        return self


class OverridePlan(CustomBaseModel):
    scenarios: list[OverrideScenario]

    @model_validator(mode="after")
    def validate_plan(self) -> "OverridePlan":
        scenario_ids = [item.scenario_id for item in self.scenarios]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise OverrideValidationError("OverridePlan contains duplicate scenario ids.")
        return self
