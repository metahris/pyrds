from __future__ import annotations

from pathlib import Path

from pyrds.domain.exceptions import ConfigError, ValidationError
from pyrds.infrastructure.config.settings import FilesPath, Settings


def resolve_working_dir(settings: Settings, name: str) -> FilesPath:
    root = _configured_root(settings)
    safe_name = _safe_dir_name(name)
    return FilesPath(
        working_dir=str(root / safe_name),
        xml_updater_path=settings.pyrds_api.xml_updater_path or None,
    )


def create_working_dir(settings: Settings, name: str) -> tuple[FilesPath, list[str]]:
    files_path = resolve_working_dir(settings=settings, name=name)
    paths = [
        files_path.working_dir,
        files_path.inputs,
        files_path.data,
        files_path.trade,
        files_path.results,
        files_path.qml_updater,
        files_path.backtest,
    ]

    created: list[str] = []
    for path in paths:
        folder = Path(path)
        existed = folder.exists()
        folder.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(str(folder))

    return files_path, created


def _configured_root(settings: Settings) -> Path:
    root = settings.pyrds_api.pyrds_dir
    if not root:
        raise ConfigError("config pyrds_api.pyrds_dir is required to create or resolve working dirs.")
    return Path(root).expanduser().resolve()


def _safe_dir_name(name: str) -> str:
    value = name.strip()
    if not value:
        raise ValidationError("Working directory name cannot be empty.")

    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValidationError("Working directory name must be relative and cannot contain '..'.")

    if len(path.parts) != 1:
        raise ValidationError("Working directory name must be a single folder name.")

    return value
