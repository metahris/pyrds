from __future__ import annotations

from typing import Any


def merge_log_context(base: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    context = dict(base or {})
    for key, value in kwargs.items():
        if value is not None:
            context[key] = value
    return context


def log_info(logger: Any, message: str, **context: Any) -> None:
    if logger is None:
        return
    logger.info("%s | %s", message, context)


def log_warning(logger: Any, message: str, **context: Any) -> None:
    if logger is None:
        return
    logger.warning("%s | %s", message, context)


def log_error(logger: Any, message: str, **context: Any) -> None:
    if logger is None:
        return
    logger.error("%s | %s", message, context)


def log_exception(logger: Any, message: str, **context: Any) -> None:
    if logger is None:
        return
    logger.exception("%s | %s", message, context)
