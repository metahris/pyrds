from __future__ import annotations

from pyrds.application.runners.stress_runner import StressRunner
from pyrds.application.services.qml_handler import QmlHandler
from pyrds.domain.stress_models import build_stress_request


def test_stress_runner_uploads_stress_qml_as_market_data_key(working_dir, logger) -> None:
    runner = StressRunner(
        logger=logger,
        files_path=working_dir,
        qml_handler=QmlHandler(logger=logger),
        ps_api=object(),
        market_api=object(),
        trades_api=object(),
        request_set_tags={"request", "instructionset"},
    )

    market_data = runner.get_mkt_data_qmls()

    assert "BERM_STRESS" in market_data
    assert "<stress>" in market_data["BERM_STRESS"]

    runner.verify_stress_request(
        qml_data=market_data,
        stresses_request=build_stress_request(
            {
                "stress_name": "BERM_STRESS",
                "deformations": {
                    "rates": {
                        "name": "RateLevel",
                        "mult": {"type": "scalar", "value": 1},
                        "add": {"type": "scalar", "value": 0},
                    }
                },
            }
        ),
    )
