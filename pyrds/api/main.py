from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError
from fastapi.responses import JSONResponse

from pyrds.api.dependencies import get_client
from pyrds.api.routes.backtest import router as backtest_router
from pyrds.api.routes.computing import router as computing_router
from pyrds.api.routes.health import router as health_router
from pyrds.api.routes.overrides import router as overrides_router
from pyrds.api.routes.qlib import router as qlib_router
from pyrds.api.routes.results import router as results_router
from pyrds.api.routes.stress import router as stress_router
from pyrds.api.routes.working_dir import router as working_dir_router
from pyrds.api.static_loader import load_api_metadata, load_api_tags
from pyrds.domain.exceptions import (
    APIError,
    AuthError,
    BatchRequestError,
    ConfigError,
    DumpError,
    OverrideApplicationError,
    OverrideValidationError,
    QmlInputNotFoundError,
    QmlVerificationError,
    RequestTimeoutError,
    ResultParsingError,
    SDKError,
    SerializationError,
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
app.include_router(working_dir_router)
app.include_router(computing_router)
app.include_router(backtest_router)
app.include_router(stress_router)
app.include_router(qlib_router)
app.include_router(overrides_router)
app.include_router(results_router)


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


@app.exception_handler(SerializationError)
async def handle_serialization_error(_, exc: SerializationError) -> JSONResponse:
    return error_response(status_code=400, error_type="serialization_error", detail=str(exc))


@app.exception_handler(ResultParsingError)
async def handle_result_parsing_error(_, exc: ResultParsingError) -> JSONResponse:
    return error_response(status_code=400, error_type="result_parsing_error", detail=str(exc))


@app.exception_handler(QmlInputNotFoundError)
async def handle_qml_input_not_found_error(_, exc: QmlInputNotFoundError) -> JSONResponse:
    return error_response(status_code=404, error_type="qml_input_not_found", detail=str(exc))


@app.exception_handler(QmlVerificationError)
async def handle_qml_verification_error(_, exc: QmlVerificationError) -> JSONResponse:
    return error_response(status_code=400, error_type="qml_verification_error", detail=str(exc))


@app.exception_handler(DumpError)
async def handle_dump_error(_, exc: DumpError) -> JSONResponse:
    return error_response(status_code=500, error_type="dump_error", detail=str(exc))


@app.exception_handler(OverrideValidationError)
async def handle_override_validation_error(_, exc: OverrideValidationError) -> JSONResponse:
    return error_response(status_code=400, error_type="override_validation_error", detail=str(exc))


@app.exception_handler(OverrideApplicationError)
async def handle_override_application_error(_, exc: OverrideApplicationError) -> JSONResponse:
    return error_response(status_code=400, error_type="override_application_error", detail=str(exc))


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
