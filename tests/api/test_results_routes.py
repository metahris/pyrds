from __future__ import annotations

from fastapi.testclient import TestClient

from pyrds.api.dependencies import get_client, get_settings
from pyrds.api.main import app
from tests.conftest import DELTAIR_RESULT_QML, PRICE_RESULT_QML, VEGAIR_RESULT_QML


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
    assert "/results/parse/vector/{instruction_name}" not in paths


def test_docs_use_pinned_swagger_ui_assets(monkeypatch) -> None:
    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    with TestClient(app) as client:
        response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui-dist@5.17.14/swagger-ui-bundle.js" in response.text
    assert "swagger-ui-dist@5.17.14/swagger-ui.css" in response.text
    assert "swagger-ui-dist@5/swagger-ui-bundle.js" not in response.text
