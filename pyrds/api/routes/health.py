from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
