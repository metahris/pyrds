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
    ADD_FILE = "add_file"
    ADD_FILES = "add_files"
    REPLACE_FILE = "replace_file"
    REPLACE_BLOCK = "replace_block"
    REPLACE_BLOCKS = "replace_blocks"
    REPLACE_XPATH = "replace_xpath"
    SET_XPATH_TEXT = "set_xpath_text"
    SET_XPATH_ATTRIBUTE = "set_xpath_attribute"


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


class TargetQmlSource(CustomBaseModel):
    target_id: str
    source: QmlSource


class QmlOverride(CustomBaseModel):
    name: str
    target_type: OverrideTargetType
    operation: OverrideOperation
    target_id: str | None = None
    target_ids: list[str] | None = None
    target_sources: list[TargetQmlSource] | None = None
    apply_to_all: bool = False
    source: QmlSource | None = None
    sources: list[QmlSource] | None = None
    xpath: str | None = None
    attribute: str | None = None
    value: str | None = None
    match_policy: MatchPolicy = MatchPolicy.EXACTLY_ONE
    allow_duplicate_tags: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_override(self) -> "QmlOverride":
        target_selectors = [
            bool(self.target_id),
            bool(self.target_ids),
            bool(self.target_sources),
            self.apply_to_all,
        ]
        if sum(1 for selected in target_selectors if selected) > 1:
            raise OverrideValidationError(
                f"Override '{self.name}' must set only one of target_id, target_ids, "
                "target_sources, apply_to_all."
            )

        requires_target_selector = self.target_type in {
            OverrideTargetType.MARKETDATA,
            OverrideTargetType.PRODUCT,
            OverrideTargetType.PRICINGPARAMS,
        } and self.operation not in {OverrideOperation.ADD_FILE, OverrideOperation.ADD_FILES}
        if (
            not self.apply_to_all
            and not self.target_id
            and not self.target_ids
            and not self.target_sources
            and requires_target_selector
        ):
            raise OverrideValidationError(
                f"Override '{self.name}' requires target_id, target_ids, target_sources, "
                "or apply_to_all=True."
            )

        if self.target_ids is not None and not self.target_ids:
            raise OverrideValidationError(f"Override '{self.name}' target_ids cannot be empty.")

        if self.target_sources is not None:
            if not self.target_sources:
                raise OverrideValidationError(f"Override '{self.name}' target_sources cannot be empty.")
            if self.operation not in {
                OverrideOperation.ADD_FILES,
                OverrideOperation.REPLACE_FILE,
                OverrideOperation.REPLACE_BLOCK,
                OverrideOperation.REPLACE_XPATH,
            }:
                raise OverrideValidationError(
                    f"Override '{self.name}' target_sources is only supported for "
                    "add_files, replace_file, replace_block, and replace_xpath."
                )
            target_ids = [item.target_id for item in self.target_sources]
            if len(target_ids) != len(set(target_ids)):
                raise OverrideValidationError(f"Override '{self.name}' target_sources contains duplicate target ids.")

        if self.operation == OverrideOperation.ADD_FILE:
            if self.target_type != OverrideTargetType.MARKETDATA:
                raise OverrideValidationError(f"Override '{self.name}' add_file is only supported for marketdata.")
            if self.source is None:
                raise OverrideValidationError(f"Override '{self.name}' requires source.")
        elif self.operation == OverrideOperation.ADD_FILES:
            if self.target_type != OverrideTargetType.MARKETDATA:
                raise OverrideValidationError(f"Override '{self.name}' add_files is only supported for marketdata.")
            if not self.sources and not self.target_sources:
                raise OverrideValidationError(f"Override '{self.name}' requires sources or target_sources.")
        elif self.operation in {OverrideOperation.REPLACE_FILE, OverrideOperation.REPLACE_BLOCK}:
            if self.source is None and self.target_sources is None:
                raise OverrideValidationError(f"Override '{self.name}' requires source.")
        elif self.operation == OverrideOperation.REPLACE_BLOCKS:
            if not self.sources:
                raise OverrideValidationError(f"Override '{self.name}' requires sources.")
        elif self.operation == OverrideOperation.REPLACE_XPATH:
            if self.source is None and self.target_sources is None:
                raise OverrideValidationError(f"Override '{self.name}' requires source.")
            if not self.xpath:
                raise OverrideValidationError(
                    f"Override '{self.name}' requires source and xpath."
                )
        elif self.operation == OverrideOperation.SET_XPATH_TEXT:
            if self.value is None or not self.xpath:
                raise OverrideValidationError(
                    f"Override '{self.name}' requires value and xpath."
                )
        elif self.operation == OverrideOperation.SET_XPATH_ATTRIBUTE:
            if self.value is None or not self.xpath or not self.attribute:
                raise OverrideValidationError(
                    f"Override '{self.name}' requires value, xpath, and attribute."
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
