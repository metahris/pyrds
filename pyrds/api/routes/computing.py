from __future__ import annotations

from fastapi import APIRouter, Depends

from pyrds.api.dependencies import get_client, get_settings
from pyrds.api.logging import log_api_event, ps_request_context
from pyrds.api.schemas import (
    CustomMarketDataComputeRequest,
    FullQmlComputeFromWorkingDirRequest,
    HybridComputeRequest,
    OtComputeRequest,
)
from pyrds.api.working_dir import resolve_working_dir
from pyrds.domain.ps_request import UseCache
from pyrds.infrastructure.config.settings import Settings
from pyrds.sdk.client import PyrdsClient

router = APIRouter(prefix="/computing", tags=["Computing"])


@router.post("/generic/ot", response_model=dict[str, str])
def compute_generic_ot(
    request: OtComputeRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    log_api_event(
        "Computing generic OT started",
        dir=request.pyrds_dir,
        **ps_request_context(request.ps_request),
    )
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_generic_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    result = runner.compute_ot(ps_request=request.ps_request, dump=True)
    log_api_event("Computing generic OT finished", dir=request.pyrds_dir, result_count=len(result))
    return result


@router.post("/generic/full-qml", response_model=dict[str, str])
def compute_generic_full_qml(
    request: FullQmlComputeFromWorkingDirRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    log_api_event(
        "Computing generic full QML started",
        dir=request.pyrds_dir,
        **ps_request_context(request.ps_request),
    )
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_generic_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    result = runner.compute_full_qml(
        ps_request=request.ps_request,
        use_cache_factory=UseCache,
        dump=True,
    )
    log_api_event("Computing generic full QML finished", dir=request.pyrds_dir, result_count=len(result))
    return result


@router.post("/generic/custom-market-data", response_model=dict[str, str])
def compute_generic_custom_market_data(
    request: CustomMarketDataComputeRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    log_api_event(
        "Computing custom market data started",
        dir=request.pyrds_dir,
        **ps_request_context(request.ps_request),
    )
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_generic_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    result = runner.compute_custom_mkt_data(
        ps_request=request.ps_request,
        use_cache_factory=UseCache,
        dump=True,
    )
    log_api_event("Computing custom market data finished", dir=request.pyrds_dir, result_count=len(result))
    return result


@router.post("/generic/hybrid", response_model=dict[str, str])
def compute_generic_hybrid(
    request: HybridComputeRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    log_api_event(
        "Computing hybrid started",
        dir=request.pyrds_dir,
        **ps_request_context(request.ps_request),
    )
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_hybrid_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    result = runner.compute_hybrid(
        ps_request=request.ps_request,
        use_cache_factory=UseCache,
        dump=True,
    )
    log_api_event("Computing hybrid finished", dir=request.pyrds_dir, result_count=len(result))
    return result


def _build_qml_handler(client: PyrdsClient):
    from pyrds.application.services.qml_handler import QmlHandler

    return QmlHandler(logger=client.logger)
