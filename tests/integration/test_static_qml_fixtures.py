from __future__ import annotations

from pathlib import Path

import pytest

from pyrds.application.services.qml_handler import QmlHandler
from pyrds.application.services.qml_input_service import QmlInputService
from pyrds.infrastructure.config.settings import FilesPath


STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"
pytestmark = pytest.mark.skipif(
    not STATIC_ROOT.exists(),
    reason="tests/static fixture tree is not present in this checkout.",
)


def _files_path(root: Path) -> FilesPath:
    return FilesPath(working_dir=str(root))


def test_generic_static_fixture_loads_market_data_and_trade_qmls(logger) -> None:
    root = STATIC_ROOT / "generic"
    files_path = _files_path(root)
    handler = QmlHandler(logger=logger)
    service = QmlInputService(qml_handler=handler, files_path=files_path, logger=logger)

    market_data = service.get_market_data_qmls(request_set_tags={"request", "instructionset"})
    product = service.get_product_qml()
    pricing_params = service.get_pricing_params_qml()

    assert market_data
    assert all(handler.get_root_tag(qml) not in {"request", "instructionset", "results", "stress"} for qml in market_data.values())
    assert product["trade_id"]
    assert product["product_qml"]
    assert pricing_params


def test_stress_static_fixture_request_can_be_updated(logger) -> None:
    root = STATIC_ROOT / "stress"
    request_file = root / "inputs" / "data" / "price-28405308-request.xml"
    if not request_file.exists():
        pytest.skip("stress request fixture is not present.")

    handler = QmlHandler(logger=logger)
    request_qml = handler.load_qml(str(request_file))
    updated = handler.update_request_with_mult_add_shift_scenarios(
        request_qml=request_qml,
        stresses_request={
            "stresses": [
                {
                    "name": "BERM_STRESS",
                    "vectorAffineDeformations": [
                        {
                            "affineDeformations": [
                                {"deformation": "RateLevel", "factors": {"add": 0.0, "mult": -5.0}},
                                {"deformation": "SigmaShock", "factors": {"add": 0.0, "mult": 10.0}},
                            ]
                        }
                    ],
                }
            ]
        },
    )

    assert handler.get_root_tag(updated) == "request"
    assert "MULTI BYSCENARIO" in updated
    assert "<refKey>BERM_STRESS</refKey>" in updated


def test_delta_vega_static_result_can_be_parsed(logger) -> None:
    result_file = STATIC_ROOT / "delta_vega" / "resultMult.xml"
    if not result_file.exists():
        pytest.skip("delta_vega/resultMult.xml fixture is not present.")

    handler = QmlHandler(logger=logger)
    result_qml = handler.load_qml(str(result_file))

    assert handler.parse_result_deltair(result_qml=result_qml) is not None
    assert handler.parse_result_vegair(result_qml=result_qml) is not None


def test_backtest_static_fixture_contains_historical_folder(logger) -> None:
    data_root = STATIC_ROOT / "backtest" / "inputs" / "data"
    historical_folders = [item for item in data_root.iterdir() if item.is_dir()]
    if not historical_folders:
        pytest.skip("backtest historical data folders are not present.")

    handler = QmlHandler(logger=logger)
    qmls = handler.load_qmls(str(historical_folders[0]))

    assert qmls
    assert any(item["data_type"] == "instructionset" for item in qmls.values())
    assert any(item["data_type"] == "request" for item in qmls.values())
