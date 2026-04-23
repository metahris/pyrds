from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from pyrds.api.dependencies import get_client, get_settings
from pyrds.api.main import app
from pyrds.api.working_dir import create_working_dir
from tests.conftest import DELTAIR_RESULT_QML, PRICE_RESULT_QML, VEGAIR_RESULT_QML

FUNC_DURATION_TEMPLATE = """
<results version="2">
  <request version="2">
    <product>{product}</product>
  </request>
  <instruction name="PRICE" type="PRICE" version="3">
    <base version="2">
      <funcDuration>
        <item>
          <key>qlib::FunctionA</key>
          <val>
            <duration>{function_a}</duration>
            <nbIter>1</nbIter>
          </val>
        </item>
        <item>
          <key>qlib::FunctionB</key>
          <val>
            <duration>{function_b}</duration>
            <nbIter>2</nbIter>
          </val>
        </item>
      </funcDuration>
    </base>
  </instruction>
  <instruction name="VEGAIR" type="HEDGE" version="2">
    <base version="2">
      <funcDuration>
        <item>
          <key>qlib::FunctionA</key>
          <val>
            <duration>{function_a_extra}</duration>
            <nbIter>3</nbIter>
          </val>
        </item>
      </funcDuration>
    </base>
  </instruction>
</results>
"""

PRICE_EXCEL_TEMPLATE = """
<results>
  <request>
    <product>{product}</product>
  </request>
  <instruction name="PRICE">
    <base>
      <duration>123</duration>
    </base>
    <output>
      <item name="total">
        <price>{total}</price>
        <currency>USD</currency>
      </item>
      <item name="underlying">
        <price>{underlying}</price>
        <currency>USD</currency>
      </item>
      <item name="option">
        <price>{option}</price>
        <currency>USD</currency>
      </item>
    </output>
  </instruction>
</results>
"""


class DummyClient:
    logger = None

    async def aclose(self) -> None:
        return None


def test_parse_price_inline_xml(settings, monkeypatch) -> None:
    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_client] = lambda: DummyClient()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/results/parse/price",
                json={"inline_xml": PRICE_RESULT_QML},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"]["PRICE"]["total"] == {"price": "42.5", "currency": "USD"}


def test_parse_deltair_inline_xml(settings, monkeypatch) -> None:
    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_client] = lambda: DummyClient()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/results/parse/deltair",
                json={"inline_xml": DELTAIR_RESULT_QML},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["parsed"][0]["curve"] == "USD_SOFR"


def test_parse_vegair_inline_xml(settings, monkeypatch) -> None:
    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_client] = lambda: DummyClient()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/results/parse/vegair",
                json={"inline_xml": VEGAIR_RESULT_QML},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["parsed"][0]["items"][0]["points"][0]["tenor"] == "5Y"


def test_parse_duration_result_file(settings, monkeypatch) -> None:
    files_path, _ = create_working_dir(settings=settings, name="duration-work")
    Path(files_path.results, "result.xml").write_text(PRICE_RESULT_QML, encoding="utf-8")

    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_client] = lambda: DummyClient()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/results/parse/duration",
                json={"dir": "duration-work", "file_name": "result.xml"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["parsed"] == {"product_name": "TradeA", "duration": 123}


def test_parse_duration_all_xml_files_dumps_product_duration_excel(settings, monkeypatch) -> None:
    files_path, _ = create_working_dir(settings=settings, name="duration-excel-work")
    results_dir = Path(files_path.results)
    (results_dir / "first.xml").write_text(PRICE_RESULT_QML, encoding="utf-8")
    (results_dir / "second.xml").write_text(
        PRICE_RESULT_QML.replace("TradeA", "TradeB").replace("<duration>123</duration>", "<duration>456</duration>"),
        encoding="utf-8",
    )

    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_client] = lambda: DummyClient()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/results/parse/duration",
                json={
                    "dir": "duration-excel-work",
                    "file_name": "all",
                    "dump_excel": True,
                    "excel_file_name": "durations.xlsx",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"]["first.xml"] == {"product_name": "TradeA", "duration": 123}
    assert payload["parsed"]["second.xml"] == {"product_name": "TradeB", "duration": 456}

    import pandas as pd

    rows = pd.read_excel(payload["excel_path"]).to_dict(orient="records")
    assert rows == [
        {"product": "TradeA", "duration": 123},
        {"product": "TradeB", "duration": 456},
    ]


def test_parse_price_all_xml_files(settings, monkeypatch) -> None:
    files_path, _ = create_working_dir(settings=settings, name="all-work")
    results_dir = Path(files_path.results)
    (results_dir / "first.xml").write_text(PRICE_RESULT_QML, encoding="utf-8")
    nested_dir = results_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "second.xml").write_text(PRICE_RESULT_QML.replace("42.5", "84.0"), encoding="utf-8")
    (results_dir / "ignored.txt").write_text(PRICE_RESULT_QML, encoding="utf-8")

    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_client] = lambda: DummyClient()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/results/parse/price",
                json={"dir": "all-work", "file_name": "all"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    parsed = response.json()["parsed"]
    assert sorted(parsed) == ["first.xml", "nested/second.xml"]
    assert parsed["first.xml"]["PRICE"]["total"]["price"] == "42.5"
    assert parsed["nested/second.xml"]["PRICE"]["total"]["price"] == "84.0"


def test_parse_price_all_xml_files_dumps_compact_price_excel(settings, monkeypatch) -> None:
    files_path, _ = create_working_dir(settings=settings, name="price-excel-work")
    results_dir = Path(files_path.results)
    (results_dir / "first.xml").write_text(
        PRICE_EXCEL_TEMPLATE.format(product="ProductA", total="36156", underlying="34320", option="18358"),
        encoding="utf-8",
    )
    (results_dir / "second.xml").write_text(
        PRICE_EXCEL_TEMPLATE.format(product="ProductB", total="10.5", underlying="8", option="2.5"),
        encoding="utf-8",
    )

    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_client] = lambda: DummyClient()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/results/parse/price",
                json={
                    "dir": "price-excel-work",
                    "file_name": "all",
                    "dump_excel": True,
                    "excel_file_name": "prices.xlsx",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"]["first.xml"]["product_name"] == "ProductA"

    import pandas as pd

    rows = pd.read_excel(payload["excel_path"]).to_dict(orient="records")
    assert rows == [
        {"product": "ProductA", "total": 36156.0, "underlying": 34320, "option": 18358.0, "currency": "USD"},
        {"product": "ProductB", "total": 10.5, "underlying": 8, "option": 2.5, "currency": "USD"},
    ]


def test_parse_func_duration_all_xml_files_dumps_product_function_excel(settings, monkeypatch) -> None:
    files_path, _ = create_working_dir(settings=settings, name="func-duration-work")
    results_dir = Path(files_path.results)
    (results_dir / "first.xml").write_text(
        FUNC_DURATION_TEMPLATE.format(
            product="ProductA",
            function_a="10.5",
            function_b="3.0",
            function_a_extra="2.5",
        ),
        encoding="utf-8",
    )
    (results_dir / "second.xml").write_text(
        FUNC_DURATION_TEMPLATE.format(
            product="ProductB",
            function_a="20",
            function_b="4",
            function_a_extra="6",
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_client] = lambda: DummyClient()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/results/parse/func-duration",
                json={
                    "dir": "func-duration-work",
                    "file_name": "all",
                    "dump_excel": True,
                    "excel_file_name": "func_duration.xlsx",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed"]["first.xml"]["functions"]["qlib::FunctionA"] == 13.0
    assert payload["parsed"]["second.xml"]["functions"]["qlib::FunctionA"] == 26.0

    import pandas as pd

    workbook = pd.ExcelFile(payload["excel_path"])
    assert workbook.sheet_names == ["PRICE", "VEGAIR"]

    price_rows = pd.read_excel(workbook, sheet_name="PRICE").to_dict(orient="records")
    assert price_rows == [
        {"product": "ProductA", "FunctionA": 10.5, "FunctionB": 3},
        {"product": "ProductB", "FunctionA": 20.0, "FunctionB": 4},
    ]

    vegair_rows = pd.read_excel(workbook, sheet_name="VEGAIR").to_dict(orient="records")
    assert vegair_rows == [
        {"product": "ProductA", "FunctionA": 2.5},
        {"product": "ProductB", "FunctionA": 6.0},
    ]


def test_openapi_contains_expected_public_routes(monkeypatch) -> None:
    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    paths = response.json()["paths"]
    assert "/computing/generic/ot" in paths
    assert "/computing/generic/full-qml" in paths
    assert "/backtest/full-qml" in paths
    assert "/stress/full-qml" in paths
    assert "/qlib/regression-validation" in paths
    assert "/overrides/ot" in paths
    assert "/results/parse/price" in paths
    assert "/results/parse/duration" in paths
    assert "/results/parse/func-duration" in paths
    assert "/results/parse/vector/{instruction_name}" not in paths


def test_docs_use_pinned_swagger_ui_assets(monkeypatch) -> None:
    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    with TestClient(app) as client:
        response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui-dist@5.17.14/swagger-ui-bundle.js" in response.text
    assert "swagger-ui-dist@5.17.14/swagger-ui.css" in response.text
    assert "swagger-ui-dist@5/swagger-ui-bundle.js" not in response.text
