from __future__ import annotations

from pathlib import Path

import pytest

from pyrds.api.working_dir import create_working_dir, resolve_working_dir
from pyrds.domain.exceptions import QmlInputNotFoundError, ValidationError
from pyrds.infrastructure.config.settings import Settings


def test_settings_apply_shared_api_defaults(settings: Settings) -> None:
    assert settings.env == "preprod"
    assert settings.market_data_api.resolved_host == "https://preprod.example"
    assert settings.trade_api.authentication.resolved_token("preprod") == "token"
    assert settings.ps_api.proxies == {"http": "", "https": ""}


def test_create_working_dir_creates_expected_layout(settings: Settings) -> None:
    files_path, created = create_working_dir(settings=settings, name="sample")

    assert Path(files_path.working_dir).is_dir()
    assert Path(files_path.data).is_dir()
    assert Path(files_path.trade).is_dir()
    assert Path(files_path.results).is_dir()
    assert Path(files_path.qml_updater).is_dir()
    assert not (Path(files_path.working_dir) / "backtest").exists()
    assert created


def test_resolve_working_dir_rejects_unsafe_name(settings: Settings) -> None:
    with pytest.raises(ValidationError):
        resolve_working_dir(settings=settings, name="../outside")


def test_resolve_working_dir_requires_existing_directory(settings: Settings) -> None:
    with pytest.raises(QmlInputNotFoundError, match="Create it first with POST /working-dir"):
        resolve_working_dir(settings=settings, name="missing")
