from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field, model_validator

from pyrds.domain.override_models import OverridePlan
from pyrds.domain.ps_request import PsRequest


class CreateWorkingDirRequest(BaseModel):
    dir: str = Field(description="Working directory name under config pyrds_api.pyrds_dir.")


class WorkingDirResponse(BaseModel):
    name: str
    root_path: str
    working_dir: str
    inputs: str
    data: str
    trade: str
    results: str
    logs: str
    qml_updater: str
    created: list[str]


class ComputeFromWorkingDirRequest(BaseModel):
    pyrds_dir: str = Field(
        validation_alias=AliasChoices("pyrds_dir", "dir"),
        description="Working directory name created under config pyrds_api.pyrds_dir.",
    )
    ps_request: PsRequest


class FullQmlComputeFromWorkingDirRequest(ComputeFromWorkingDirRequest):
    pass


class CustomMarketDataComputeRequest(ComputeFromWorkingDirRequest):
    pass


class OtComputeRequest(ComputeFromWorkingDirRequest):
    pass


class HybridComputeRequest(ComputeFromWorkingDirRequest):
    pass


class BacktestFullQmlRequest(ComputeFromWorkingDirRequest):
    carto: str = Field(description="Cartography token used to normalize historical market data names.")


class StressComputeRequest(ComputeFromWorkingDirRequest):
    stress: dict[str, Any] = Field(description="Compact stress definition converted to StressRequest internally.")


class QlibRegressionValidationRequest(ComputeFromWorkingDirRequest):
    ref_version: str = Field(
        validation_alias=AliasChoices("ref_version", "ref"),
        description="Reference Qlib version.",
    )
    new_version: str = Field(
        validation_alias=AliasChoices("new_version", "new"),
        description="New Qlib version to compare against the reference.",
    )
    dump_xl: bool = Field(default=False, description="Write the comparison as an Excel file in results.")


class OverrideComputeRequest(ComputeFromWorkingDirRequest):
    override_plan: OverridePlan
    dump: bool = Field(default=True, description="Write raw scenario result XML files in results.")
    dump_excel: bool = Field(default=True, description="Write an override summary Excel file in results.")


class ResultXmlParseRequest(BaseModel):
    inline_xml: str | None = Field(default=None, description="Raw result XML content.")
    pyrds_dir: str | None = Field(
        default=None,
        validation_alias=AliasChoices("pyrds_dir", "dir"),
        description="Working directory name under config pyrds_api.pyrds_dir.",
    )
    file_name: str | None = Field(
        default=None,
        description="Result XML file name or relative path under the working directory results folder.",
    )
    dump_excel: bool = Field(default=False, description="Write parsed output as an Excel file in results.")
    excel_file_name: str | None = Field(default=None, description="Optional Excel file name when dump_excel=true.")

    @model_validator(mode="after")
    def validate_source(self) -> "ResultXmlParseRequest":
        has_inline = bool(self.inline_xml)
        has_file = bool(self.pyrds_dir and self.file_name)
        if has_inline == has_file:
            raise ValueError("Provide exactly one source: inline_xml or both dir/pyrds_dir and file_name.")
        return self


class ParsedResultResponse(BaseModel):
    parsed: Any
    excel_path: str | None = None


class ErrorResponse(BaseModel):
    type: str
    detail: str
    status_code: int
    errors: Any | None = None
