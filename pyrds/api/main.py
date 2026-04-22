from __future__ import annotations

from contextlib import asynccontextmanager
import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import ValidationError as PydanticValidationError
from fastapi.responses import JSONResponse, Response

from pyrds.api.dependencies import get_client, get_settings
from pyrds.api.logging import api_logger, log_api_event
from pyrds.api.routes.backtest import router as backtest_router
from pyrds.api.routes.computing import router as computing_router
from pyrds.api.routes.health import router as health_router
from pyrds.api.routes.overrides import router as overrides_router
from pyrds.api.routes.qlib import router as qlib_router
from pyrds.api.routes.results import router as results_router
from pyrds.api.routes.stress import router as stress_router
from pyrds.api.routes.working_dir import router as working_dir_router
from pyrds.api.static_loader import load_api_metadata, load_api_tags
from pyrds.api.working_dir import build_working_dir_path, resolve_working_dir
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
from pyrds.logger import activate_log_session, attach_file_handler, deactivate_log_session, detach_handler


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
    settings = get_settings()
    request_payload = await _read_request_payload(request)
    log_file_path = _resolve_log_file_path(request=request, payload=request_payload, settings=settings)
    handler = None
    token = None
    if log_file_path is not None:
        session_id = uuid4().hex
        token = activate_log_session(session_id)
        handler = attach_file_handler(api_logger, file_path=log_file_path, session_id=session_id)

    log_api_event(
        "API request started",
        method=request.method,
        path=request.url.path,
        log_file=log_file_path,
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
        if handler is not None:
            _append_terminal_response_dump(
                file_path=log_file_path,
                status_code=500,
                content_type="text/plain",
                body=f"Unhandled exception before response: {exc.__class__.__name__}".encode("utf-8"),
            )
            detach_handler(api_logger, handler)
        if token is not None:
            deactivate_log_session(token)
        raise

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response_body = await _read_response_body(response)
    log_api_event(
        "API request finished",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    if handler is not None:
        _append_terminal_response_dump(
            file_path=log_file_path,
            status_code=response.status_code,
            content_type=response.headers.get("content-type"),
            body=response_body,
        )
        detach_handler(api_logger, handler)
    if token is not None:
        deactivate_log_session(token)
    return _rebuild_response(response=response, body=response_body)


async def _read_request_payload(request: Request) -> Any | None:
    body = await request.body()

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # type: ignore[attr-defined]
    if not body:
        return None
    if "application/json" not in request.headers.get("content-type", "").lower():
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _resolve_log_file_path(*, request: Request, payload: Any, settings: Any) -> str | None:
    if not isinstance(payload, dict):
        return None

    dir_name = payload.get("pyrds_dir") or payload.get("dir")
    if not isinstance(dir_name, str) or not dir_name.strip():
        return None

    try:
        if request.url.path == "/working-dir":
            working_dir = build_working_dir_path(settings=settings, name=dir_name)
            logs_dir = working_dir / "logs"
        else:
            files_path = resolve_working_dir(settings=settings, name=dir_name)
            logs_dir = Path(files_path.logs)
    except Exception:
        return None

    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    route_name = request.url.path.strip("/").replace("/", "_") or "root"
    file_name = f"{timestamp}_{request.method.lower()}_{route_name}_{uuid4().hex[:8]}.txt"
    return str(logs_dir / file_name)


async def _read_response_body(response: Response) -> bytes:
    if hasattr(response, "body") and response.body is not None:
        return bytes(response.body)

    if not hasattr(response, "body_iterator") or response.body_iterator is None:
        return b""

    chunks: list[bytes] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
    return b"".join(chunks)


def _rebuild_response(*, response: Response, body: bytes) -> Response:
    return Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=response.background,
    )


def _append_terminal_response_dump(
    *,
    file_path: str | None,
    status_code: int,
    content_type: str | None,
    body: bytes,
) -> None:
    if not file_path:
        return

    text_body = _format_response_body(body=body, content_type=content_type)
    with Path(file_path).open("a", encoding="utf-8") as file_handle:
        file_handle.write("\n=== FINAL RESPONSE ===\n")
        file_handle.write(f"status_code: {status_code}\n")
        if content_type:
            file_handle.write(f"content_type: {content_type}\n")
        file_handle.write("body:\n")
        file_handle.write(text_body)
        file_handle.write("\n")


def _format_response_body(*, body: bytes, content_type: str | None) -> str:
    if not body:
        return "<empty>"

    decoded = body.decode("utf-8", errors="replace")
    if content_type and "application/json" in content_type.lower():
        try:
            return json.dumps(json.loads(decoded), indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            return decoded
    return decoded


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
