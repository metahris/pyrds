from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from pyrds.api.dependencies import get_client, get_settings
from pyrds.api.logging import log_api_event, ps_request_context
from pyrds.api.schemas import OverrideComputeRequest
from pyrds.api.working_dir import resolve_working_dir
from pyrds.domain.ps_request import UseCache
from pyrds.infrastructure.config.settings import Settings
from pyrds.sdk.client import PyrdsClient

router = APIRouter(prefix="/overrides", tags=["Overrides"])


@router.post("/ot", response_model=dict[str, dict[str, Any]])
async def override_ot(
    request: OverrideComputeRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, dict[str, Any]]:
    log_api_event(
        "Override OT started",
        dir=request.pyrds_dir,
        scenario_count=len(request.override_plan.scenarios),
        **ps_request_context(request.ps_request),
    )
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_override_qml_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    result = await runner.compute_override_ot_async(
        ps_request=request.ps_request,
        override_plan=request.override_plan,
        use_cache_factory=UseCache,
        dump=request.dump,
        dump_excel=request.dump_excel,
    )
    log_api_event("Override OT finished", dir=request.pyrds_dir, scenario_count=len(result))
    return result


@router.post("/full-qml", response_model=dict[str, dict[str, Any]])
async def override_full_qml(
    request: OverrideComputeRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, dict[str, Any]]:
    log_api_event(
        "Override full QML started",
        dir=request.pyrds_dir,
        scenario_count=len(request.override_plan.scenarios),
        **ps_request_context(request.ps_request),
    )
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_override_qml_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    result = await runner.compute_override_full_qml_async(
        ps_request=request.ps_request,
        override_plan=request.override_plan,
        use_cache_factory=UseCache,
        dump=request.dump,
        dump_excel=request.dump_excel,
    )
    log_api_event("Override full QML finished", dir=request.pyrds_dir, scenario_count=len(result))
    return result


def _build_qml_handler(client: PyrdsClient):
    from pyrds.application.services.qml_handler import QmlHandler

    return QmlHandler(logger=client.logger)
