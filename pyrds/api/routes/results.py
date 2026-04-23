from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

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
    handler = _build_qml_handler(client)
    parsed, excel_dir = _parse_result_request(
        request=request,
        settings=settings,
        parser=lambda qml: _parse_price_with_product(handler=handler, qml=qml),
    )
    excel_path = _dump_excel_if_requested(
        request=request,
        parsed=parsed,
        excel_dir=excel_dir,
        default_name="price_result.xlsx",
        rows_builder=_price_rows_for_excel,
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
    handler = _build_qml_handler(client)
    parsed, excel_dir = _parse_result_request(
        request=request,
        settings=settings,
        parser=lambda qml: handler.parse_result_deltair(result_qml=qml),
    )
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
    handler = _build_qml_handler(client)
    parsed, excel_dir = _parse_result_request(
        request=request,
        settings=settings,
        parser=lambda qml: handler.parse_result_vegair(result_qml=qml),
    )
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
    handler = _build_qml_handler(client)
    parsed, excel_dir = _parse_result_request(
        request=request,
        settings=settings,
        parser=lambda qml: handler.parse_calibrator_results(result_qml=qml),
    )
    excel_path = _dump_excel_if_requested(
        request=request,
        parsed=parsed,
        excel_dir=excel_dir,
        default_name="calibration_result.xlsx",
    )
    log_api_event("Parse calibration result finished", excel_path=excel_path)
    return ParsedResultResponse(parsed=parsed, excel_path=excel_path)


@router.post("/parse/duration", response_model=ParsedResultResponse)
def parse_duration_result(
    request: ResultXmlParseRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> ParsedResultResponse:
    log_api_event("Parse duration result started", source=_source_label(request), dump_excel=request.dump_excel)
    handler = _build_qml_handler(client)
    parsed, excel_dir = _parse_result_request(
        request=request,
        settings=settings,
        parser=lambda qml: _parse_duration_with_product(handler=handler, qml=qml),
    )
    excel_path = _dump_excel_if_requested(
        request=request,
        parsed=parsed,
        excel_dir=excel_dir,
        default_name="duration_result.xlsx",
        rows_builder=_duration_rows_for_excel,
    )
    log_api_event("Parse duration result finished", excel_path=excel_path)
    return ParsedResultResponse(parsed=parsed, excel_path=excel_path)


@router.post("/parse/func-duration", response_model=ParsedResultResponse)
def parse_func_duration_result(
    request: ResultXmlParseRequest,
    client: PyrdsClient = Depends(get_client),
    settings: Settings = Depends(get_settings),
) -> ParsedResultResponse:
    log_api_event("Parse function duration result started", source=_source_label(request), dump_excel=request.dump_excel)
    handler = _build_qml_handler(client)
    parsed, excel_dir = _parse_result_request(
        request=request,
        settings=settings,
        parser=lambda qml: handler.parse_result_func_duration(result_qml=qml),
    )
    excel_path = _dump_excel_if_requested(
        request=request,
        parsed=parsed,
        excel_dir=excel_dir,
        default_name="func_duration_result.xlsx",
        workbook_writer=_write_func_duration_excel,
    )
    log_api_event("Parse function duration result finished", excel_path=excel_path)
    return ParsedResultResponse(parsed=parsed, excel_path=excel_path)


def _source_label(request: ResultXmlParseRequest) -> str:
    if request.inline_xml:
        return "inline_xml"
    return f"{request.pyrds_dir}/{request.file_name}"


def _parse_price_with_product(*, handler: Any, qml: str) -> dict[str, Any]:
    parsed = handler.parse_result_price(result_qml=qml)
    if isinstance(parsed, dict):
        parsed.setdefault("product_name", handler.get_product_name(qml))
    return parsed


def _parse_duration_with_product(*, handler: Any, qml: str) -> dict[str, Any]:
    return {
        "product_name": handler.get_product_name(qml),
        "duration": handler.get_pricing_duration(result_qml=qml),
    }


def _parse_result_request(
    *,
    request: ResultXmlParseRequest,
    settings: Settings,
    parser: Callable[[str], Any],
) -> tuple[Any, Path | None]:
    qml_by_source, excel_dir = _load_result_qmls(request=request, settings=settings)
    if len(qml_by_source) == 1 and not _is_all_files_request(request):
        return parser(next(iter(qml_by_source.values()))), excel_dir

    return {source: parser(qml) for source, qml in qml_by_source.items()}, excel_dir


def _load_result_qmls(request: ResultXmlParseRequest, settings: Settings) -> tuple[dict[str, str], Path | None]:
    if request.inline_xml:
        return {"inline_xml": request.inline_xml}, None

    if not request.pyrds_dir or not request.file_name:
        raise ValidationError("dir/pyrds_dir and file_name are required when inline_xml is not provided.")

    files_path = resolve_working_dir(settings=settings, name=request.pyrds_dir)
    results_dir = Path(files_path.results).resolve()

    if _is_all_files_request(request):
        return _load_all_result_qmls(results_dir=results_dir), results_dir

    file_path = _safe_result_file_path(results_dir=results_dir, file_name=request.file_name)
    return {_relative_result_source(results_dir=results_dir, file_path=file_path): _read_result_file(file_path)}, results_dir


def _load_all_result_qmls(*, results_dir: Path) -> dict[str, str]:
    qml_by_source: dict[str, str] = {}
    xml_paths = sorted(path for path in results_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".xml")
    for file_path in xml_paths:
        qml_by_source[_relative_result_source(results_dir=results_dir, file_path=file_path)] = _read_result_file(file_path)
    return qml_by_source


def _read_result_file(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise QmlInputNotFoundError(f"Result XML file does not exist: {file_path}") from exc
    except Exception as exc:
        raise SerializationError(f"Failed to load result XML file: {file_path}") from exc


def _is_all_files_request(request: ResultXmlParseRequest) -> bool:
    return bool(request.file_name and request.file_name.strip().lower() == "all")


def _relative_result_source(*, results_dir: Path, file_path: Path) -> str:
    return file_path.relative_to(results_dir).as_posix()


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
    rows_builder: Callable[[Any], list[dict[str, Any]]] | None = None,
    workbook_writer: Callable[[Any, Path], None] | None = None,
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

        if workbook_writer:
            workbook_writer(parsed, excel_path)
        else:
            rows = rows_builder(parsed) if rows_builder else _flatten_for_excel(parsed)
            pd.DataFrame(rows or [{"value": None}]).to_excel(excel_path, index=False)
    except Exception as exc:
        raise DumpError(f"Failed to write parsed Excel file: {excel_path}") from exc

    return str(excel_path)


def _write_func_duration_excel(parsed: Any, excel_path: Path) -> None:
    import pandas as pd

    sheets = _func_duration_sheets_for_excel(parsed)
    if not sheets:
        sheets = {"func_duration": [{"product_name": None}]}
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        used_sheet_names: set[str] = set()
        for instruction_name, rows in sheets.items():
            sheet_name = _excel_sheet_name(instruction_name, used_sheet_names=used_sheet_names)
            pd.DataFrame(rows or [{"product_name": None}]).to_excel(writer, sheet_name=sheet_name, index=False)


def _price_rows_for_excel(parsed: Any) -> list[dict[str, Any]]:
    if _looks_like_price_payload(parsed):
        return [_price_row(parsed, fallback_product=None)]

    if isinstance(parsed, dict):
        rows: list[dict[str, Any]] = []
        for source, item in parsed.items():
            if _looks_like_price_payload(item):
                rows.append(_price_row(item, fallback_product=source))
        if rows:
            return rows

    return _flatten_for_excel(parsed)


def _duration_rows_for_excel(parsed: Any) -> list[dict[str, Any]]:
    if _looks_like_duration_payload(parsed):
        return [_duration_row(parsed, fallback_product=None)]

    if isinstance(parsed, dict):
        rows: list[dict[str, Any]] = []
        for source, item in parsed.items():
            if _looks_like_duration_payload(item):
                rows.append(_duration_row(item, fallback_product=source))
        if rows:
            return rows

    return _flatten_for_excel(parsed)


def _looks_like_duration_payload(value: Any) -> bool:
    return isinstance(value, dict) and "duration" in value


def _duration_row(value: dict[str, Any], *, fallback_product: str | None) -> dict[str, Any]:
    return {
        "product": value.get("product_name") or fallback_product,
        "duration": value.get("duration"),
    }


def _looks_like_price_payload(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("PRICE"), dict)


def _price_row(value: dict[str, Any], *, fallback_product: str | None) -> dict[str, Any]:
    price_items = value.get("PRICE") or {}
    row: dict[str, Any] = {"product": value.get("product_name") or fallback_product}
    currency: Any = None

    for item_name, item in price_items.items():
        if not isinstance(item, dict):
            continue

        column = str(item_name).strip().lower() or "price"
        row[column] = _coerce_numeric_for_excel(item.get("price"))
        currency = currency or item.get("currency")

    row["currency"] = currency
    return row


def _coerce_numeric_for_excel(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        numeric = float(value)
    except ValueError:
        return value
    if numeric.is_integer():
        return int(numeric)
    return numeric


def _func_duration_sheets_for_excel(parsed: Any) -> dict[str, list[dict[str, Any]]]:
    sheets: dict[str, list[dict[str, Any]]] = {}

    if _looks_like_func_duration_payload(parsed):
        _add_func_duration_rows(sheets=sheets, payload=parsed, fallback_product_name=None)
        return sheets

    if isinstance(parsed, dict):
        for source, item in parsed.items():
            if _looks_like_func_duration_payload(item):
                _add_func_duration_rows(sheets=sheets, payload=item, fallback_product_name=source)
                continue

            if isinstance(item, dict):
                for scenario, scenario_item in item.items():
                    if _looks_like_func_duration_payload(scenario_item):
                        _add_func_duration_rows(
                            sheets=sheets,
                            payload=scenario_item,
                            fallback_product_name=f"{source}:{scenario}",
                        )
        return sheets

    return {"func_duration": _flatten_for_excel(parsed)}


def _add_func_duration_rows(
    *,
    sheets: dict[str, list[dict[str, Any]]],
    payload: dict[str, Any],
    fallback_product_name: str | None,
) -> None:
    product_name = payload.get("product_name") or fallback_product_name
    for instruction_name, functions in (payload.get("instructions") or {}).items():
        row: dict[str, Any] = {"product": product_name}
        for function_name, metrics in functions.items():
            column = _short_function_name(str(function_name))
            if isinstance(metrics, dict):
                row[column] = metrics.get("duration")
            else:
                row[column] = metrics
        sheets.setdefault(str(instruction_name), []).append(row)


def _looks_like_func_duration_payload(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("functions"), dict)


def _excel_sheet_name(value: str, *, used_sheet_names: set[str]) -> str:
    safe_name = "".join("_" if char in "[]:*?/\\" else char for char in value).strip() or "Sheet"
    sheet_name = safe_name[:31]
    index = 1
    while sheet_name in used_sheet_names:
        suffix = f"_{index}"
        sheet_name = f"{safe_name[: 31 - len(suffix)]}{suffix}"
        index += 1
    used_sheet_names.add(sheet_name)
    return sheet_name


def _short_function_name(value: str) -> str:
    return value.rsplit("::", 1)[-1]


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
