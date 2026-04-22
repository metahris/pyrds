from __future__ import annotations

import contextvars
import logging
from pathlib import Path
from typing import Any


class CustomFormatter(logging.Formatter):
    blue = "\x1b[38;5;123m"
    orange = "\x1b[38;5;209m"
    green = "\x1b[38;5;9m"
    light_red = "\x1b[38;5;4m"
    red = "\x1b[38;5;9m"
    reset = "\x1b[0m"
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: blue + log_format + reset,
        logging.INFO: green + log_format + reset,
        logging.WARNING: orange + log_format + reset,
        logging.ERROR: light_red + log_format + reset,
        logging.CRITICAL: red + log_format + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        formatter = logging.Formatter(self.FORMATS.get(record.levelno, self.log_format))
        return formatter.format(record)


class PlainFormatter(logging.Formatter):
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    def __init__(self) -> None:
        super().__init__(self.log_format)


_active_log_session: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "active_log_session",
    default=None,
)


class RequestLogFilter(logging.Filter):
    def __init__(self, session_id: str) -> None:
        super().__init__()
        self.session_id = session_id

    def filter(self, record: logging.LogRecord) -> bool:
        return _active_log_session.get() == self.session_id


def init_logger(name: str, level: str = "debug") -> logging.Logger:
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    logging_level = level_map.get(level.lower(), logging.DEBUG)

    logger = logging.getLogger(name)
    logger.setLevel(logging_level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(CustomFormatter())
        logger.addHandler(handler)

    for handler in logger.handlers:
        handler.setLevel(logging_level)

    return logger


def attach_file_handler(logger: logging.Logger, *, file_path: str, session_id: str) -> logging.Handler:
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(file_path, encoding="utf-8")
    handler.setLevel(logger.level)
    handler.setFormatter(PlainFormatter())
    handler.addFilter(RequestLogFilter(session_id))
    logger.addHandler(handler)
    return handler


def detach_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    logger.removeHandler(handler)
    handler.flush()
    handler.close()


def activate_log_session(session_id: str) -> contextvars.Token[Any]:
    return _active_log_session.set(session_id)


def deactivate_log_session(token: contextvars.Token[Any]) -> None:
    _active_log_session.reset(token)
