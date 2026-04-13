from __future__ import annotations

from fastapi import APIRouter, Depends

from pyrds.api.dependencies import get_client, get_settings
from pyrds.api.schemas import BacktestFullQmlRequest
from pyrds.api.working_dir import resolve_working_dir
from pyrds.domain.ps_request import UseCache
from pyrds.infrastructure.config.settings import Settings
from pyrds.sdk.client import PyrdsClient

router = APIRouter(prefix="/backtest", tags=["Backtest"])


@router.post("/full-qml", response_model=dict[str, str])
async def backtest_full_qml(
    request: BacktestFullQmlRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    runner = client.create_backtester(
        files_path=files_path,
        qml_handler=_build_qml_handler(client),
        request_set_tags={"request", "instructionset"},
    )
    return await runner.backtest(
        ps_request=request.ps_request,
        carto=request.carto,
        use_cache_factory=UseCache,
        dump=True,
        return_result=True,
    )


def _build_qml_handler(client: PyrdsClient):
    from pyrds.application.services.qml_handler import QmlHandler

    return QmlHandler(logger=client.logger)
