from __future__ import annotations

from types import SimpleNamespace

from pyrds.api.dependencies import get_client
from pyrds.api.logging import api_logger


def test_get_client_uses_api_logger(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_client(*, settings, logger):
        captured["settings"] = settings
        captured["logger"] = logger
        return SimpleNamespace(logger=logger)

    get_client.cache_clear()
    try:
        monkeypatch.setattr("pyrds.api.dependencies.get_settings", lambda: "SETTINGS")
        monkeypatch.setattr("pyrds.api.dependencies.PyrdsClient", fake_client)
        client = get_client()
        assert client.logger is api_logger
        assert captured == {"settings": "SETTINGS", "logger": api_logger}
    finally:
        get_client.cache_clear()
