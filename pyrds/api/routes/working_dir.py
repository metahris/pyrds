from __future__ import annotations

from fastapi import APIRouter, Depends

from pyrds.api.dependencies import get_settings
from pyrds.api.schemas import CreateWorkingDirRequest, WorkingDirResponse
from pyrds.api.working_dir import create_working_dir
from pyrds.infrastructure.config.settings import Settings

router = APIRouter(prefix="/working-dir", tags=["Working Dir"])


@router.post("", response_model=WorkingDirResponse)
def create_pyrds_working_dir(
    request: CreateWorkingDirRequest,
    settings: Settings = Depends(get_settings),
) -> WorkingDirResponse:
    files_path, created = create_working_dir(settings=settings, name=request.dir)
    return WorkingDirResponse(
        name=request.dir,
        root_path=settings.pyrds_api.pyrds_dir or "",
        working_dir=files_path.working_dir,
        inputs=files_path.inputs,
        data=files_path.data,
        trade=files_path.trade,
        results=files_path.results,
        qml_updater=files_path.qml_updater,
        backtest=files_path.backtest,
        created=created,
    )
