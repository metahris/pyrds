from __future__ import annotations

from fastapi import APIRouter, Depends

from pyrds.api.dependencies import get_settings
from pyrds.api.logging import log_api_event
from pyrds.api.schemas import CreateWorkingDirRequest, WorkingDirResponse
from pyrds.api.working_dir import create_working_dir
from pyrds.infrastructure.config.settings import Settings

router = APIRouter(prefix="/working-dir", tags=["Working Dir"])


@router.post("", response_model=WorkingDirResponse)
def create_pyrds_working_dir(
    request: CreateWorkingDirRequest,
    settings: Settings = Depends(get_settings),
) -> WorkingDirResponse:
    log_api_event("Creating working directory", dir=request.dir)
    files_path, created = create_working_dir(settings=settings, name=request.dir)
    log_api_event(
        "Working directory ready",
        dir=request.dir,
        working_dir=files_path.working_dir,
        created_count=len(created),
    )
    return WorkingDirResponse(
        name=request.dir,
        root_path=settings.pyrds_api.pyrds_dir or "",
        working_dir=files_path.working_dir,
        inputs=files_path.inputs,
        data=files_path.data,
        trade=files_path.trade,
        results=files_path.results,
        qml_updater=files_path.qml_updater,
        created=created,
    )
