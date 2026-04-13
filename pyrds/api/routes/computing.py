from __future__ import annotations

from fastapi import APIRouter, Depends

from pyrds.api.dependencies import get_client, get_settings
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
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_generic_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    return runner.compute_ot(ps_request=request.ps_request, dump=True)


@router.post("/generic/full-qml", response_model=dict[str, str])
def compute_generic_full_qml(
    request: FullQmlComputeFromWorkingDirRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_generic_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    return runner.compute_full_qml(
        ps_request=request.ps_request,
        use_cache_factory=UseCache,
        dump=True,
    )


@router.post("/generic/custom-market-data", response_model=dict[str, str])
def compute_generic_custom_market_data(
    request: CustomMarketDataComputeRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_generic_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    return runner.compute_custom_mkt_data(
        ps_request=request.ps_request,
        use_cache_factory=UseCache,
        dump=True,
    )


@router.post("/generic/hybrid", response_model=dict[str, str])
def compute_generic_hybrid(
    request: HybridComputeRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_hybrid_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    return runner.compute_hybrid(
        ps_request=request.ps_request,
        use_cache_factory=UseCache,
        dump=True,
    )


def _build_qml_handler(client: PyrdsClient):
    from pyrds.application.services.qml_handler import QmlHandler

    return QmlHandler(logger=client.logger)
