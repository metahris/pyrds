from __future__ import annotations

from types import SimpleNamespace

import pytest

from pyrds.application.services.qml_handler import QmlHandler
from pyrds.domain.exceptions import QmlVerificationError, ResultParsingError
from tests.conftest import (
    CALIBRATION_RESULT_QML,
    DELTAIR_RESULT_QML,
    INSTRUCTION_SET_QML,
    PRICE_RESULT_QML,
    REQUEST_QML,
    VEGAIR_RESULT_QML,
)


def test_load_qmls_reads_only_xml_files(working_dir, logger) -> None:
    handler = QmlHandler(logger=logger)

    qmls = handler.load_qmls(working_dir.data)

    assert "cache" not in qmls
    assert qmls["request"]["data_type"] == "request"
    assert qmls["instructionset"]["data_type"] == "instructionset"
    assert qmls["MODEL_304_48_172_SNE"]["data_type"] == "model"


def test_verify_request_qml_normalizes_container_placeholders(logger) -> None:
    handler = QmlHandler(logger=logger)

    verified = handler.verify_request_qml(request_qml=REQUEST_QML)

    assert "<product>!{PRODUCT}</product>" in verified
    assert "<instructionset>!{INSTRUCTIONSET}</instructionset>" in verified
    assert "<pricingparam>!{PRICINGPARAM}</pricingparam>" in verified
    assert "<distribute>true</distribute>" in verified
    assert logger.contains("Verifying request QML")
    assert logger.contains("Request QML verified")


def test_verify_instruction_set_qml_accepts_matching_request_date(logger, ps_request) -> None:
    handler = QmlHandler(logger=logger)

    handler.verify_instruction_set_qml(
        instruction_set_qml=INSTRUCTION_SET_QML,
        ps_request=ps_request,
    )
    assert logger.contains("Verifying instruction set QML")
    assert logger.contains("Instruction set QML verified")


def test_verify_instruction_set_qml_rejects_wrong_market_data_env(logger, ps_request) -> None:
    handler = QmlHandler(logger=logger)
    qml = INSTRUCTION_SET_QML.replace("<mktdataenv>BASE</mktdataenv>", "<mktdataenv>HISTO</mktdataenv>")

    with pytest.raises(QmlVerificationError):
        handler.verify_instruction_set_qml(instruction_set_qml=qml, ps_request=ps_request)


def test_get_valdate_from_price_instruction(logger) -> None:
    handler = QmlHandler(logger=logger)

    assert handler.get_valdate_from_price_instruction(INSTRUCTION_SET_QML) == "2024/01/02 23:59:59"


def test_update_request_with_mult_add_shift_scenarios_builds_multi_byscenario(logger) -> None:
    handler = QmlHandler(logger=logger)
    stress_request = SimpleNamespace(
        stresses=[
            SimpleNamespace(
                name="BERM_STRESS",
                vectorAffineDeformations=[
                    {
                        "affineDeformations": [
                            {"deformation": "RateLevel", "factors": {"add": 0.0, "mult": -5.0}},
                            {"deformation": "SigmaShock", "factors": {"add": 0.0, "mult": 10.0}},
                        ]
                    }
                ],
            )
        ]
    )

    updated = handler.update_request_with_mult_add_shift_scenarios(
        request_qml=REQUEST_QML,
        stresses_request=stress_request,
    )

    assert '<request type="MULTI BYSCENARIO" version="4">' in updated
    assert "<base_request version=\"5\">" in updated
    assert "<count>1</count>" in updated
    assert "<refKey>BERM_STRESS</refKey>" in updated
    assert "<key>RateLevel</key>" in updated
    assert "<key>SigmaShock</key>" in updated


def test_parse_price_result_extracts_total_duration_and_currency(logger) -> None:
    handler = QmlHandler(logger=logger)

    parsed = handler.parse_result_price(result_qml=PRICE_RESULT_QML)

    assert parsed["PRICE"]["total"] == {"price": "42.5", "currency": "USD"}
    assert parsed["price"]["PRICE"]["total"] == {"price": "42.5", "currency": "USD"}
    assert handler.get_pricing_duration(result_qml=PRICE_RESULT_QML) == 123


def test_parse_deltair_result_extracts_vector_points(logger) -> None:
    handler = QmlHandler(logger=logger)

    parsed = handler.parse_result_deltair(result_qml=DELTAIR_RESULT_QML)

    assert parsed == [
        {
            "curve": "USD_SOFR",
            "items": [
                {
                    "item": "total",
                    "points": [
                        {"maturity": "1Y", "value": 1.5},
                        {"maturity": "2Y", "value": 2.5},
                    ],
                }
            ],
        }
    ]


def test_parse_vegair_result_splits_maturity_and_tenor(logger) -> None:
    handler = QmlHandler(logger=logger)

    parsed = handler.parse_result_vegair(result_qml=VEGAIR_RESULT_QML)

    assert parsed[0]["curve"] == "USD_VOL"
    assert parsed[0]["items"][0]["points"][0] == {"maturity": "1Y", "tenor": "5Y", "value": 3.5}


def test_parse_calibration_result_extracts_calibration_info(logger) -> None:
    handler = QmlHandler(logger=logger)

    parsed = handler.parse_calibrator_results(result_qml=CALIBRATION_RESULT_QML)

    assert parsed["product_name"] == "TradeA"
    assert parsed["PRICE"] == {
        "calibration_info": "calibration info",
        "calibration_result": "OK",
    }


def test_update_block_in_qml_raises_when_block_is_missing(logger) -> None:
    handler = QmlHandler(logger=logger)

    with pytest.raises(ResultParsingError):
        handler.update_block_in_qml(
            qml="<product><notional>100</notional></product>",
            block="<coupon>2</coupon>",
            data_id="trade",
        )
