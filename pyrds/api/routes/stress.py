from __future__ import annotations

from fastapi import APIRouter, Depends

from pyrds.api.dependencies import get_client, get_settings
from pyrds.api.logging import log_api_event, ps_request_context
from pyrds.api.schemas import StressComputeRequest
from pyrds.api.working_dir import resolve_working_dir
from pyrds.domain.exceptions import ValidationError
from pyrds.domain.stress_models import build_stress_request
from pyrds.infrastructure.config.settings import Settings
from pyrds.sdk.client import PyrdsClient

router = APIRouter(prefix="/stress", tags=["Stress"])


@router.post("/full-qml", response_model=dict[str, str])
def stress_full_qml(
    request: StressComputeRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    log_api_event(
        "Stress full QML started",
        dir=request.pyrds_dir,
        stress_name=request.stress.get("stress_name"),
        **ps_request_context(request.ps_request),
    )
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_stress_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    result = runner.compute_stress_full_qml(
        ps_request=request.ps_request,
        stresses_request=_build_stress_request(request.stress),
        dump=True,
    )
    log_api_event("Stress full QML finished", dir=request.pyrds_dir, result_count=len(result))
    return result


@router.post("/ot", response_model=dict[str, str])
def stress_ot(
    request: StressComputeRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    log_api_event(
        "Stress OT started",
        dir=request.pyrds_dir,
        stress_name=request.stress.get("stress_name"),
        **ps_request_context(request.ps_request),
    )
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_stress_runner(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    result = runner.compute_stress_ot(
        ps_request=request.ps_request,
        stresses_request=_build_stress_request(request.stress),
        dump=True,
    )
    log_api_event("Stress OT finished", dir=request.pyrds_dir, result_count=len(result))
    return result


def _build_stress_request(stress: dict):
    try:
        return build_stress_request(stress)
    except Exception as exc:
        raise ValidationError(f"Invalid stress payload: {exc}") from exc


def _build_qml_handler(client: PyrdsClient):
    from pyrds.application.services.qml_handler import QmlHandler

    return QmlHandler(logger=client.logger)
