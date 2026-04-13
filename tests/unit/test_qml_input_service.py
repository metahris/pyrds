from __future__ import annotations

from pyrds.application.services.qml_handler import QmlHandler
from pyrds.application.services.qml_input_service import QmlInputService


REQUEST_SET_TAGS = {"request", "instructionset"}


def test_get_market_data_qmls_excludes_request_instructionset_results_and_stress(working_dir, logger) -> None:
    service = QmlInputService(
        qml_handler=QmlHandler(logger=logger),
        files_path=working_dir,
        logger=logger,
    )

    market_data = service.get_market_data_qmls(request_set_tags=REQUEST_SET_TAGS)

    assert set(market_data) == {"MODEL_304_48_172_SNE"}
    assert "<model>" in market_data["MODEL_304_48_172_SNE"]


def test_market_data_base_suffix_is_uploaded_with_pipe_base_key(working_dir, logger) -> None:
    from pathlib import Path

    Path(working_dir.data, "ycsetup_BASE.xml").write_text("<ycsetup />", encoding="utf-8")
    service = QmlInputService(
        qml_handler=QmlHandler(logger=logger),
        files_path=working_dir,
        logger=logger,
    )

    market_data = service.get_market_data_qmls(request_set_tags=REQUEST_SET_TAGS)

    assert "ycsetup|BASE" in market_data
    assert "ycsetup_BASE" not in market_data


def test_get_trade_qmls_selects_product_and_pricing_params(working_dir, logger) -> None:
    service = QmlInputService(
        qml_handler=QmlHandler(logger=logger),
        files_path=working_dir,
        logger=logger,
    )

    product = service.get_product_qml()
    pricing_params = service.get_pricing_params_qml()

    assert product["trade_id"] == "price-28405308-product"
    assert "<product>" in product["product_qml"]
    assert "<pricingparams>" in pricing_params


def test_get_request_qml_returns_verified_request(working_dir, logger) -> None:
    service = QmlInputService(
        qml_handler=QmlHandler(logger=logger),
        files_path=working_dir,
        logger=logger,
    )

    request_qml = service.get_request_qml()

    assert "<product>!{PRODUCT}</product>" in request_qml
    assert "<distribute>true</distribute>" in request_qml
