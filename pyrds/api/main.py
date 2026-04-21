from __future__ import annotations

from contextlib import asynccontextmanager
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import ValidationError as PydanticValidationError
from fastapi.responses import JSONResponse

from pyrds.api.dependencies import get_client
from pyrds.api.logging import log_api_event
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
    PricingComputationError,
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
SWAGGER_UI_DIST_VERSION = "5.17.14"
app = FastAPI(
    title=metadata.get("title", "Pyrds"),
    description=metadata.get("description"),
    version=metadata.get("version", "3.0.0"),
    contact=metadata.get("contact"),
    openapi_tags=load_api_tags(),
    docs_url=None,
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


@app.get("/docs", include_in_schema=False)
async def swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url=(
            f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_DIST_VERSION}/swagger-ui-bundle.js"
        ),
        swagger_css_url=(
            f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_DIST_VERSION}/swagger-ui.css"
        ),
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_ui_parameters=app.swagger_ui_parameters,
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    log_api_event(
        "API request started",
        method=request.method,
        path=request.url.path,
    )
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        log_api_event(
            "API request failed",
            method=request.method,
            path=request.url.path,
            duration_ms=duration_ms,
            error=exc.__class__.__name__,
        )
        raise

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    log_api_event(
        "API request finished",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response


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
    log_api_event("API request validation failed", errors=jsonable_encoder(exc.errors()))
    return error_response(
        status_code=422,
        error_type="request_validation_error",
        detail="Request validation failed.",
        errors=jsonable_encoder(exc.errors()),
    )


@app.exception_handler(PydanticValidationError)
async def handle_pydantic_validation_error(_, exc: PydanticValidationError) -> JSONResponse:
    log_api_event("API payload validation failed", errors=jsonable_encoder(exc.errors()))
    return error_response(
        status_code=422,
        error_type="payload_validation_error",
        detail="Payload validation failed.",
        errors=jsonable_encoder(exc.errors()),
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(_, exc: HTTPException) -> JSONResponse:
    log_api_event("API HTTP exception", status_code=exc.status_code, detail=str(exc.detail))
    return error_response(
        status_code=exc.status_code,
        error_type="http_error",
        detail=str(exc.detail),
    )


@app.exception_handler(ConfigError)
async def handle_config_error(_, exc: ConfigError) -> JSONResponse:
    log_api_event("API config error", error=str(exc))
    return error_response(status_code=500, error_type="config_error", detail=str(exc))


@app.exception_handler(AuthError)
async def handle_auth_error(_, exc: AuthError) -> JSONResponse:
    log_api_event("API auth error", error=str(exc))
    return error_response(status_code=502, error_type="auth_error", detail=str(exc))


@app.exception_handler(ValidationError)
async def handle_validation_error(_, exc: ValidationError) -> JSONResponse:
    log_api_event("API validation error", error=str(exc))
    return error_response(status_code=400, error_type="validation_error", detail=str(exc))


@app.exception_handler(SerializationError)
async def handle_serialization_error(_, exc: SerializationError) -> JSONResponse:
    log_api_event("API serialization error", error=str(exc))
    return error_response(status_code=400, error_type="serialization_error", detail=str(exc))


@app.exception_handler(ResultParsingError)
async def handle_result_parsing_error(_, exc: ResultParsingError) -> JSONResponse:
    log_api_event("API result parsing error", error=str(exc))
    return error_response(status_code=400, error_type="result_parsing_error", detail=str(exc))


@app.exception_handler(QmlInputNotFoundError)
async def handle_qml_input_not_found_error(_, exc: QmlInputNotFoundError) -> JSONResponse:
    log_api_event("API QML input not found", error=str(exc))
    return error_response(status_code=404, error_type="qml_input_not_found", detail=str(exc))


@app.exception_handler(QmlVerificationError)
async def handle_qml_verification_error(_, exc: QmlVerificationError) -> JSONResponse:
    log_api_event("API QML verification error", error=str(exc))
    return error_response(status_code=400, error_type="qml_verification_error", detail=str(exc))


@app.exception_handler(DumpError)
async def handle_dump_error(_, exc: DumpError) -> JSONResponse:
    log_api_event("API dump error", error=str(exc))
    return error_response(status_code=500, error_type="dump_error", detail=str(exc))


@app.exception_handler(PricingComputationError)
async def handle_pricing_computation_error(_, exc: PricingComputationError) -> JSONResponse:
    log_api_event("API pricing computation error", error=str(exc))
    return error_response(status_code=502, error_type="pricing_computation_error", detail=str(exc))


@app.exception_handler(OverrideValidationError)
async def handle_override_validation_error(_, exc: OverrideValidationError) -> JSONResponse:
    log_api_event("API override validation error", error=str(exc))
    return error_response(status_code=400, error_type="override_validation_error", detail=str(exc))


@app.exception_handler(OverrideApplicationError)
async def handle_override_application_error(_, exc: OverrideApplicationError) -> JSONResponse:
    log_api_event("API override application error", error=str(exc))
    return error_response(status_code=400, error_type="override_application_error", detail=str(exc))


@app.exception_handler(APIError)
async def handle_api_error(_, exc: APIError) -> JSONResponse:
    status_code = exc.status_code or 502
    log_api_event("API upstream error", status_code=status_code, url=exc.url, error=str(exc))
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
    log_api_event("API upstream timeout", url=exc.url, error=str(exc))
    return error_response(
        status_code=504,
        error_type="request_timeout",
        detail=str(exc),
        errors={"url": exc.url},
    )


@app.exception_handler(TransportError)
async def handle_transport_error(_, exc: TransportError) -> JSONResponse:
    log_api_event("API transport error", url=exc.url, error=str(exc))
    return error_response(
        status_code=502,
        error_type="transport_error",
        detail=str(exc),
        errors={"url": exc.url, "details": exc.details},
    )


@app.exception_handler(BatchRequestError)
async def handle_batch_error(_, exc: BatchRequestError) -> JSONResponse:
    log_api_event("API batch request error", failures=list(exc.failures.keys()), error=str(exc))
    return error_response(
        status_code=502,
        error_type="batch_request_error",
        detail=str(exc),
        errors={key: str(value) for key, value in exc.failures.items()},
    )


@app.exception_handler(SDKError)
async def handle_sdk_error(_, exc: SDKError) -> JSONResponse:
    log_api_event("API SDK error", error=str(exc))
    return error_response(status_code=500, error_type="sdk_error", detail=str(exc))
