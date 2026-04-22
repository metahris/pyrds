from __future__ import annotations

from pathlib import Path

from pyrds.domain.exceptions import ConfigError, QmlInputNotFoundError, ValidationError
from pyrds.infrastructure.config.settings import FilesPath, Settings


def resolve_working_dir(settings: Settings, name: str) -> FilesPath:
    working_dir = build_working_dir_path(settings=settings, name=name)
    if not working_dir.exists():
        raise QmlInputNotFoundError(
            f"Working directory does not exist: {working_dir}. "
            "Create it first with POST /working-dir."
        )
    if not working_dir.is_dir():
        raise QmlInputNotFoundError(f"Working directory path is not a directory: {working_dir}.")

    return FilesPath(
        working_dir=str(working_dir),
        xml_updater_path=settings.pyrds_api.xml_updater_path or None,
    )


def create_working_dir(settings: Settings, name: str) -> tuple[FilesPath, list[str]]:
    files_path = FilesPath(
        working_dir=str(build_working_dir_path(settings=settings, name=name)),
        xml_updater_path=settings.pyrds_api.xml_updater_path or None,
    )
    paths = [
        files_path.working_dir,
        files_path.inputs,
        files_path.data,
        files_path.trade,
        files_path.results,
        files_path.logs,
        files_path.qml_updater,
    ]

    created: list[str] = []
    for path in paths:
        folder = Path(path)
        existed = folder.exists()
        folder.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(str(folder))

    return files_path, created


def build_working_dir_path(settings: Settings, name: str) -> Path:
    root = _configured_root(settings)
    safe_name = _safe_dir_name(name)
    return root / safe_name


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
