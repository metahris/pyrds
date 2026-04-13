from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from pyrds.api.dependencies import get_client, get_settings
from pyrds.api.logging import log_api_event
from pyrds.api.schemas import ParsedResultResponse, ResultXmlParseRequest
from pyrds.api.working_dir import resolve_working_dir
from pyrds.domain.exceptions import DumpError, QmlInputNotFoundError, SerializationError, ValidationError
from pyrds.infrastructure.config.settings import Settings
from pyrds.sdk.client import PyrdsClient

router = APIRouter(prefix="/results", tags=["Results"])


@router.post("/parse/price", response_model=ParsedResultResponse)
def parse_price_result(
    request: ResultXmlParseRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> ParsedResultResponse:
    log_api_event("Parse price result started", source=_source_label(request), dump_excel=request.dump_excel)
    qml, excel_dir = _load_result_qml(request=request, settings=settings)
    handler = _build_qml_handler(client)
    parsed = handler.parse_result_price(result_qml=qml)
    excel_path = _dump_excel_if_requested(
        request=request,
        parsed=parsed,
        excel_dir=excel_dir,
        default_name="price_result.xlsx",
    )
    log_api_event("Parse price result finished", excel_path=excel_path)
    return ParsedResultResponse(parsed=parsed, excel_path=excel_path)


@router.post("/parse/deltair", response_model=ParsedResultResponse)
def parse_deltair_result(
    request: ResultXmlParseRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> ParsedResultResponse:
    log_api_event("Parse DELTAIR result started", source=_source_label(request), dump_excel=request.dump_excel)
    qml, excel_dir = _load_result_qml(request=request, settings=settings)
    handler = _build_qml_handler(client)
    parsed = handler.parse_result_deltair(result_qml=qml)
    excel_path = _dump_excel_if_requested(
        request=request,
        parsed=parsed,
        excel_dir=excel_dir,
        default_name="deltair_result.xlsx",
    )
    log_api_event("Parse DELTAIR result finished", excel_path=excel_path)
    return ParsedResultResponse(parsed=parsed, excel_path=excel_path)


@router.post("/parse/vegair", response_model=ParsedResultResponse)
def parse_vegair_result(
    request: ResultXmlParseRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> ParsedResultResponse:
    log_api_event("Parse VEGAIR result started", source=_source_label(request), dump_excel=request.dump_excel)
    qml, excel_dir = _load_result_qml(request=request, settings=settings)
    handler = _build_qml_handler(client)
    parsed = handler.parse_result_vegair(result_qml=qml)
    excel_path = _dump_excel_if_requested(
        request=request,
        parsed=parsed,
        excel_dir=excel_dir,
        default_name="vegair_result.xlsx",
    )
    log_api_event("Parse VEGAIR result finished", excel_path=excel_path)
    return ParsedResultResponse(parsed=parsed, excel_path=excel_path)


@router.post("/parse/calibration", response_model=ParsedResultResponse)
def parse_calibration_result(
    request: ResultXmlParseRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> ParsedResultResponse:
    log_api_event("Parse calibration result started", source=_source_label(request), dump_excel=request.dump_excel)
    qml, excel_dir = _load_result_qml(request=request, settings=settings)
    handler = _build_qml_handler(client)
    parsed = handler.parse_calibrator_results(result_qml=qml)
    excel_path = _dump_excel_if_requested(
        request=request,
        parsed=parsed,
        excel_dir=excel_dir,
        default_name="calibration_result.xlsx",
    )
    log_api_event("Parse calibration result finished", excel_path=excel_path)
    return ParsedResultResponse(parsed=parsed, excel_path=excel_path)


def _source_label(request: ResultXmlParseRequest) -> str:
    if request.inline_xml:
        return "inline_xml"
    return f"{request.pyrds_dir}/{request.file_name}"


def _load_result_qml(request: ResultXmlParseRequest, settings: Settings) -> tuple[str, Path | None]:
    if request.inline_xml:
        return request.inline_xml, None

    if not request.pyrds_dir or not request.file_name:
        raise ValidationError("dir/pyrds_dir and file_name are required when inline_xml is not provided.")

    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    results_dir = Path(files_path.results).resolve()
    file_path = _safe_result_file_path(results_dir=results_dir, file_name=request.file_name)

    try:
        return file_path.read_text(encoding="utf-8"), results_dir
    except FileNotFoundError as exc:
        raise QmlInputNotFoundError(f"Result XML file does not exist: {file_path}") from exc
    except Exception as exc:
        raise SerializationError(f"Failed to load result XML file: {file_path}") from exc


def _safe_result_file_path(*, results_dir: Path, file_name: str) -> Path:
    relative_path = Path(file_name)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise ValidationError("file_name must be a relative path under the working directory results folder.")

    file_path = (results_dir / relative_path).resolve()
    if not file_path.is_relative_to(results_dir):
        raise ValidationError("file_name must stay under the working directory results folder.")
    if file_path.suffix.lower() != ".xml":
        raise ValidationError("Only .xml result files can be parsed.")
    return file_path


def _dump_excel_if_requested(
    *,
    request: ResultXmlParseRequest,
    parsed: Any,
    excel_dir: Path | None,
    default_name: str,
) -> str | None:
    if not request.dump_excel:
        return None

    if excel_dir is None:
        raise ValidationError("dump_excel requires a file-based source with dir/pyrds_dir and file_name.")

    excel_file_name = request.excel_file_name or default_name
    excel_file_path = Path(excel_file_name)
    if excel_file_path.is_absolute() or ".." in excel_file_path.parts or len(excel_file_path.parts) != 1:
        raise ValidationError("excel_file_name must be a file name under the working directory results folder.")
    if not excel_file_name.endswith(".xlsx"):
        excel_file_name = f"{excel_file_name}.xlsx"

    excel_path = (excel_dir / excel_file_name).resolve()
    if not excel_path.is_relative_to(excel_dir):
        raise ValidationError("excel_file_name must stay under the working directory results folder.")

    try:
        import pandas as pd

        rows = _flatten_for_excel(parsed)
        pd.DataFrame(rows or [{"value": None}]).to_excel(excel_path, index=False)
    except Exception as exc:
        raise DumpError(f"Failed to write parsed Excel file: {excel_path}") from exc

    return str(excel_path)


def _flatten_for_excel(value: Any, *, path: str = "") -> list[dict[str, Any]]:
    if isinstance(value, dict):
        rows: list[dict[str, Any]] = []
        scalar_items: dict[str, Any] = {}
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if isinstance(item, dict | list):
                rows.extend(_flatten_for_excel(item, path=child_path))
            else:
                scalar_items[str(key)] = item
        if scalar_items:
            rows.insert(0, {"path": path, **scalar_items})
        return rows

    if isinstance(value, list):
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            child_path = f"{path}[{index}]"
            if isinstance(item, dict):
                row = {"path": child_path}
                nested_rows: list[dict[str, Any]] = []
                for key, child in item.items():
                    if isinstance(child, dict | list):
                        nested_rows.extend(_flatten_for_excel(child, path=f"{child_path}.{key}"))
                    else:
                        row[str(key)] = child
                rows.append(row)
                rows.extend(nested_rows)
            elif isinstance(item, list):
                rows.extend(_flatten_for_excel(item, path=child_path))
            else:
                rows.append({"path": child_path, "value": item})
        return rows

    return [{"path": path, "value": value}]


def _build_qml_handler(client: PyrdsClient):
    from pyrds.application.services.qml_handler import QmlHandler

    return QmlHandler(logger=client.logger)
