from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from pyrds.api.dependencies import get_client, get_settings
from pyrds.api.logging import log_api_event, ps_request_context
from pyrds.api.schemas import QlibRegressionValidationRequest
from pyrds.api.working_dir import resolve_working_dir
from pyrds.infrastructure.config.settings import Settings
from pyrds.sdk.client import PyrdsClient

router = APIRouter(prefix="/qlib", tags=["Qlib"])


@router.post("/regression-validation", response_model=dict[str, Any])
async def qlib_regression_validation(
    request: QlibRegressionValidationRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    log_api_event(
        "Qlib regression validation started",
        dir=request.pyrds_dir,
        ref_version=request.ref_version,
        new_version=request.new_version,
        **ps_request_context(request.ps_request),
    )
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_qlib_req_validator(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    result = await runner.qlib_req_validate(
        ref_version=request.ref_version,
        new_version=request.new_version,
        ps_request=request.ps_request,
        dump_xl=request.dump_xl,
    )
    log_api_event("Qlib regression validation finished", dir=request.pyrds_dir)
    return result


def _build_qml_handler(client: PyrdsClient):
    from pyrds.application.services.qml_handler import QmlHandler

    return QmlHandler(logger=client.logger)
