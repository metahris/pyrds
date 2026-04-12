from __future__ import annotations

import logging


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
