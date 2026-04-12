from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from fastapi.responses import JSONResponse

from pyrds.api.dependencies import get_client
from pyrds.api.routes.health import router as health_router
from pyrds.api.routes.pricing import router as pricing_router
from pyrds.api.static_loader import load_api_metadata, load_api_tags
from pyrds.domain.exceptions import (
    APIError,
    AuthError,
    BatchRequestError,
    ConfigError,
    RequestTimeoutError,
    SDKError,
    TransportError,
    ValidationError,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await get_client().aclose()


metadata = load_api_metadata()
app = FastAPI(
    title=metadata.get("title", "Pyrds"),
    description=metadata.get("description"),
    version=metadata.get("version", "0.1.0"),
    contact=metadata.get("contact"),
    openapi_tags=load_api_tags(),
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(pricing_router)


def error_response(
    *,
    status_code: int,
    error_type: str,
    detail: str,
    errors: Any | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": error_type,
        "detail": detail,
        "status_code": status_code,
    }
    if errors is not None:
        content["errors"] = errors
    return JSONResponse(status_code=status_code, content=content)


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(_, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        status_code=422,
        error_type="request_validation_error",
        detail="Request validation failed.",
        errors=jsonable_encoder(exc.errors()),
    )


@app.exception_handler(PydanticValidationError)
async def handle_pydantic_validation_error(_, exc: PydanticValidationError) -> JSONResponse:
    return error_response(
        status_code=422,
        error_type="payload_validation_error",
        detail="Payload validation failed.",
        errors=jsonable_encoder(exc.errors()),
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(_, exc: HTTPException) -> JSONResponse:
    return error_response(
        status_code=exc.status_code,
        error_type="http_error",
        detail=str(exc.detail),
    )


@app.exception_handler(ConfigError)
async def handle_config_error(_, exc: ConfigError) -> JSONResponse:
    return error_response(status_code=500, error_type="config_error", detail=str(exc))


@app.exception_handler(AuthError)
async def handle_auth_error(_, exc: AuthError) -> JSONResponse:
    return error_response(status_code=502, error_type="auth_error", detail=str(exc))


@app.exception_handler(ValidationError)
async def handle_validation_error(_, exc: ValidationError) -> JSONResponse:
    return error_response(status_code=400, error_type="validation_error", detail=str(exc))


@app.exception_handler(APIError)
async def handle_api_error(_, exc: APIError) -> JSONResponse:
    status_code = exc.status_code or 502
    return error_response(
        status_code=status_code,
        error_type="api_error",
        detail=str(exc),
        errors={
            "url": exc.url,
            "response_json": exc.response_json,
            "response_text": exc.response_text,
        },
    )


@app.exception_handler(RequestTimeoutError)
async def handle_timeout_error(_, exc: RequestTimeoutError) -> JSONResponse:
    return error_response(
        status_code=504,
        error_type="request_timeout",
        detail=str(exc),
        errors={"url": exc.url},
    )


@app.exception_handler(TransportError)
async def handle_transport_error(_, exc: TransportError) -> JSONResponse:
    return error_response(
        status_code=502,
        error_type="transport_error",
        detail=str(exc),
        errors={"url": exc.url, "details": exc.details},
    )


@app.exception_handler(BatchRequestError)
async def handle_batch_error(_, exc: BatchRequestError) -> JSONResponse:
    return error_response(
        status_code=502,
        error_type="batch_request_error",
        detail=str(exc),
        errors={key: str(value) for key, value in exc.failures.items()},
    )


@app.exception_handler(SDKError)
async def handle_sdk_error(_, exc: SDKError) -> JSONResponse:
    return error_response(status_code=500, error_type="sdk_error", detail=str(exc))
