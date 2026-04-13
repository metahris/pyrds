from __future__ import annotations

from types import SimpleNamespace

from pyrds.application.runners.base_runner import BaseRunner


class RecordingMarketApi:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def add_qml(self, *, set_id, market_data_id, market_data_qml, params=None) -> None:
        self.items.append((set_id, market_data_id))


class RecordingTradesApi:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def add_qml(self, *, set_id, trade_id, product_qml, pricing_parameters_qml, params=None) -> None:
        self.items.append((set_id, trade_id))


class RecordingPsApi:
    def __init__(self) -> None:
        self.items: list[tuple[str, str]] = []

    def add_qml(self, *, set_id, instruction_set_qml, request_qml, qml_runner) -> None:
        self.items.append((set_id, qml_runner))


def _runner(logger, market_api=None, trades_api=None, ps_api=None) -> BaseRunner:
    return BaseRunner(
        logger=logger,
        files_path=SimpleNamespace(),
        qml_handler=SimpleNamespace(),
        ps_api=ps_api or RecordingPsApi(),
        market_api=market_api or RecordingMarketApi(),
        trades_api=trades_api or RecordingTradesApi(),
    )


def test_add_market_data_qml_logs_each_key(logger) -> None:
    market_api = RecordingMarketApi()
    runner = _runner(logger, market_api=market_api)

    runner.add_market_data_qml(
        set_id="mkt_set",
        mkt_data={"YCSETUP|BASE": "<ycsetup />", "VOL|BASE": "<vol />"},
    )

    assert market_api.items == [("mkt_set", "YCSETUP|BASE"), ("mkt_set", "VOL|BASE")]
    assert logger.contains("Adding market data QML to set")
    assert logger.contains("YCSETUP|BASE")
    assert logger.contains("VOL|BASE")


def test_add_trade_qml_logs_trade_id(logger) -> None:
    trades_api = RecordingTradesApi()
    runner = _runner(logger, trades_api=trades_api)

    runner.add_trade_qml(
        set_id="trade_set",
        trade_id="trade_1",
        product_qml="<product />",
        pricing_params_qml="<pricingparams />",
    )

    assert trades_api.items == [("trade_set", "trade_1")]
    assert logger.contains("Adding trade QML to set")
    assert logger.contains("trade_1")


def test_add_request_qml_logs_set_and_runner(logger) -> None:
    ps_api = RecordingPsApi()
    runner = _runner(logger, ps_api=ps_api)

    runner.add_request_qml(
        set_id="request_set",
        instruction_set_qml="<instructionset />",
        request_qml="<request />",
        qml_runner="QML_RUNNER",
    )

    assert ps_api.items == [("request_set", "QML_RUNNER")]
    assert logger.contains("Adding request QML to set")
    assert logger.contains("request_set")
    assert logger.contains("QML_RUNNER")
