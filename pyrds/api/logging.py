from __future__ import annotations

from typing import Any

from pyrds.application.services.log_context import log_info
from pyrds.logger import init_logger


api_logger = init_logger("pyrds.api", level="info")


def log_api_event(message: str, **context: Any) -> None:
    log_info(api_logger, message, **context)


def ps_request_context(ps_request: Any | None) -> dict[str, Any]:
    details = getattr(ps_request, "gridPricerTechnicalDetails", None)
    return {
        "valuation_date": getattr(ps_request, "valuationDate", None),
        "qml_runner": getattr(details, "qmlRunner", None),
        "cartography": getattr(details, "cartography", None),
        "analyse_name": getattr(details, "analyseName", None),
        "fo_cluster": getattr(details, "foCluster", None),
    }
