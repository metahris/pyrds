from __future__ import annotations

from fastapi.testclient import TestClient

from pyrds.api.dependencies import get_client, get_settings
from pyrds.api.main import app


class DummyClient:
    logger = None

    async def aclose(self) -> None:
        return None


def test_health_route(monkeypatch) -> None:
    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_validation_errors_use_consistent_shape(monkeypatch) -> None:
    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_client] = lambda: DummyClient()
    try:
        with TestClient(app) as client:
            response = client.post("/results/parse/price", json={})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["type"] == "request_validation_error"


def test_domain_errors_use_consistent_shape(settings, monkeypatch) -> None:
    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            response = client.post("/working-dir", json={"dir": "../outside"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["type"] == "validation_error"


def test_result_file_not_found_returns_404(settings, monkeypatch) -> None:
    monkeypatch.setattr("pyrds.api.main.get_client", lambda: DummyClient())
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_client] = lambda: DummyClient()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/results/parse/price",
                json={"dir": "missing", "file_name": "not_found.xml"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["type"] == "qml_input_not_found"
