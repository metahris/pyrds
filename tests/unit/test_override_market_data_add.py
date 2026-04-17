from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from pyrds.application.runners.override_qml_runner import OverrideQmlRunner
from pyrds.application.services.qml_handler import QmlHandler
from pyrds.domain.exceptions import OverrideApplicationError
from pyrds.domain.override_models import OverrideScenario
from pyrds.domain.ps_request import PsRequest, UseCache
from pyrds.infrastructure.config.settings import FilesPath
from tests.conftest import PRICE_RESULT_QML, PRICING_PARAMS_QML, PRODUCT_QML


class FakeMarketApi:
    def __init__(self) -> None:
        self.added: list[tuple[str, str, str]] = []

    def create_set(self, params=None) -> str:
        return "mkt_added"

    def add_qml(self, *, set_id, market_data_id, market_data_qml, params=None) -> None:
        self.added.append((set_id, market_data_id, market_data_qml))


class FakePricingApi:
    def __init__(self) -> None:
        self.bodies: list[dict] = []

    def price(self, *, body):
        self.bodies.append(body)
        return {
            "responses": [
                {
                    "psRequestKey": "req_1",
                    "tradeId": "trade_1",
                    "rawResults": [PRICE_RESULT_QML],
                    "errors": [],
                    "marketDataSetIds": ["mkt_base"],
                    "tradeSetId": "trade_base",
                }
            ]
        }


class FakeTradesApi:
    def __init__(self) -> None:
        self.added: list[tuple[str, str, str, str]] = []

    def create_set(self, params=None) -> str:
        return "trade_new"

    async def get_trades_in_set_async(self, *, set_id):
        return ["trade_empty", "trade_missing", "trade_full"]

    async def get_specific_trade_content_async(self, *, set_id, trade_ids, fail_on_any_error=True):
        return {
            "trade_empty": {
                "productQml": PRODUCT_QML,
                "pricingParamsQml": "",
            },
            "trade_missing": {
                "productQml": PRODUCT_QML,
            },
            "trade_full": {
                "productQml": PRODUCT_QML,
                "pricingParamsQml": PRICING_PARAMS_QML,
            },
        }

    def add_qml(self, *, set_id, trade_id, product_qml, pricing_parameters_qml, params=None) -> None:
        self.added.append((set_id, trade_id, product_qml, pricing_parameters_qml))


def _runner(tmp_path: Path, logger, market_api=None, ps_api=None) -> OverrideQmlRunner:
    root = tmp_path / "work"
    (root / "inputs" / "data").mkdir(parents=True)
    (root / "inputs" / "trade").mkdir(parents=True)
    (root / "results").mkdir(parents=True)
    return OverrideQmlRunner(
        logger=logger,
        files_path=FilesPath(working_dir=str(root)),
        qml_handler=QmlHandler(logger=logger),
        ps_api=ps_api or FakePricingApi(),
        market_api=market_api or FakeMarketApi(),
        trades_api=SimpleNamespace(),
        request_set_tags={"request", "instructionset"},
    )


def _ps_request() -> PsRequest:
    return PsRequest.model_validate(
        {
            "valuationDate": "2024/01/02 23:59:59",
            "gridPricerTechnicalDetails": {
                "qmlRunner": "QML_RUNNER",
                "cartography": "FRTB",
            },
        }
    )


def test_override_ot_adds_market_data_set_next_to_base_ot_set(tmp_path: Path, logger) -> None:
    market_api = FakeMarketApi()
    ps_api = FakePricingApi()
    runner = _runner(tmp_path, logger, market_api=market_api, ps_api=ps_api)
    scenario = OverrideScenario.model_validate(
        {
            "scenario_id": "add_extra_market_data",
            "overrides": [
                {
                    "name": "add_static_data",
                    "target_type": "marketdata",
                    "operation": "add_file",
                    "target_id": "static_data|BASE",
                    "source": {"inline_xml": "<staticData><value>1</value></staticData>"},
                }
            ],
        }
    )

    result = asyncio.run(async_run_ot_scenario(runner, scenario))

    assert "raw_data" in result
    assert market_api.added == [
        ("mkt_added", "static_data|BASE", "<staticData><value>1</value></staticData>")
    ]
    assert ps_api.bodies[0]["marketDataSetIds"] == ["mkt_added", "mkt_base"]


async def async_run_ot_scenario(runner: OverrideQmlRunner, scenario: OverrideScenario):
    return await runner._run_ot_scenario(
        scenario=scenario,
        ps_request=_ps_request(),
        qml_runner="QML_RUNNER",
        base_trade_set_id="trade_base",
        base_market_data_set_id="mkt_base",
        use_cache_factory=UseCache,
        dump=False,
    )


def test_add_files_derives_market_data_key_from_base_suffix(tmp_path: Path, logger) -> None:
    runner = _runner(tmp_path, logger)
    source_path = Path(runner.files_path.data) / "YCSETUP_BASE.xml"
    source_path.write_text("<ycsetup />", encoding="utf-8")
    scenario = OverrideScenario.model_validate(
        {
            "scenario_id": "add_files",
            "overrides": [
                {
                    "name": "add_ycsetup",
                    "target_type": "marketdata",
                    "operation": "add_files",
                    "sources": [{"file_name": "YCSETUP_BASE.xml"}],
                }
            ],
        }
    )

    added = runner._resolve_added_market_data_qmls(scenario=scenario)

    assert added == {"YCSETUP|BASE": "<ycsetup />"}


def test_add_inline_market_data_requires_target_id(tmp_path: Path, logger) -> None:
    runner = _runner(tmp_path, logger)
    scenario = OverrideScenario.model_validate(
        {
            "scenario_id": "bad_inline_add",
            "overrides": [
                {
                    "name": "add_inline_without_key",
                    "target_type": "marketdata",
                    "operation": "add_file",
                    "source": {"inline_xml": "<staticData />"},
                }
            ],
        }
    )

    with pytest.raises(OverrideApplicationError):
        runner._resolve_added_market_data_qmls(scenario=scenario)


def test_pricingparams_override_allows_empty_or_missing_trade_pricingparams(tmp_path: Path, logger) -> None:
    trades_api = FakeTradesApi()
    runner = _runner(tmp_path, logger)
    runner.trades_api = trades_api
    scenario = OverrideScenario.model_validate(
        {
            "scenario_id": "replace_all_pricingparams",
            "overrides": [
                {
                    "name": "replace_all_pricingparams",
                    "target_type": "pricingparams",
                    "operation": "replace_file",
                    "apply_to_all": True,
                    "source": {
                        "inline_xml": "<pricingparams><method>NEW</method></pricingparams>",
                    },
                }
            ],
        }
    )

    new_set_id = asyncio.run(
        runner._clone_and_override_remote_trade_set(
            base_set_id="trade_base",
            scenario=scenario,
            qml_runner="QML_RUNNER",
        )
    )

    added_by_trade = {trade_id: pricing_qml for _, trade_id, _, pricing_qml in trades_api.added}
    assert new_set_id == "trade_new"
    assert added_by_trade["trade_empty"] == ""
    assert added_by_trade["trade_missing"] == ""
    assert "<method>NEW</method>" in added_by_trade["trade_full"]
