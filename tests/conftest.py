from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pyrds.infrastructure.config.settings import FilesPath, Settings


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run tests that call real external Pyrds services.",
    )
    parser.addoption(
        "--e2e-config",
        action="store",
        default=None,
        help="Optional config.json path for external service tests.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-e2e"):
        return

    skip_e2e = pytest.mark.skip(reason="Use --run-e2e to run external service tests.")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)


REQUEST_QML = """
<request version="5">
  <product>product</product>
  <instruction>PRICE</instruction>
  <instructionset>instructionset</instructionset>
  <pricingparam>pricingparams</pricingparam>
  <gridConfiguration>
    <distribute>false</distribute>
  </gridConfiguration>
</request>
"""

INSTRUCTION_SET_QML = """
<instructionset>
  <instructions>
    <item type="PRICE">
      <valdate>2024/01/02</valdate>
      <filterDateCCF>2024/01/02</filterDateCCF>
      <mktdataenv>BASE</mktdataenv>
    </item>
  </instructions>
</instructionset>
"""

PRODUCT_QML = """
<product>
  <name>TradeA</name>
  <notional>100</notional>
</product>
"""

PRICING_PARAMS_QML = """
<pricingparams>
  <method>BASE</method>
  <flag enabled="false">old</flag>
</pricingparams>
"""

MARKET_DATA_QML = """
<model>
  <curve>
    <rate>1.0</rate>
  </curve>
</model>
"""

PRICE_RESULT_QML = """
<results>
  <request>
    <product>TradeA</product>
  </request>
  <instruction name="PRICE">
    <base>
      <duration>123</duration>
    </base>
    <output>
      <item name="total">
        <price>42.5</price>
        <currency>USD</currency>
      </item>
      <item name="option">
        <price>12.0</price>
        <currency>USD</currency>
      </item>
    </output>
  </instruction>
</results>
"""

DELTAIR_RESULT_QML = """
<results>
  <instruction name="DELTAIR">
    <values>
      <hedges>
        <hedge data="USD_SOFR">
          <output>
            <item name="total">
              <vector>
                <row name="1Y">1.5</row>
                <row name="2Y">2.5</row>
              </vector>
            </item>
          </output>
        </hedge>
      </hedges>
    </values>
  </instruction>
</results>
"""

VEGAIR_RESULT_QML = """
<results>
  <instruction name="VEGAIR">
    <values>
      <hedges>
        <hedge data="USD_VOL">
          <output>
            <item name="total">
              <vector>
                <row name="1Y-5Y">3.5</row>
                <row name="2Y-10Y">4.5</row>
              </vector>
            </item>
          </output>
        </hedge>
      </hedges>
    </values>
  </instruction>
</results>
"""

CALIBRATION_RESULT_QML = """
<results>
  <request>
    <product>TradeA</product>
  </request>
  <instruction name="PRICE">
    <calibratorResults>
      <calibrationinfo>calibration info</calibrationinfo>
      <calibrationresult>OK</calibrationresult>
    </calibratorResults>
  </instruction>
</results>
"""


class SpyLogger:
    def __init__(self) -> None:
        self.messages: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def info(self, *args: Any, **kwargs: Any) -> None:
        self.messages.append(("info", args, kwargs))

    def warning(self, *args: Any, **kwargs: Any) -> None:
        self.messages.append(("warning", args, kwargs))

    def error(self, *args: Any, **kwargs: Any) -> None:
        self.messages.append(("error", args, kwargs))

    def debug(self, *args: Any, **kwargs: Any) -> None:
        self.messages.append(("debug", args, kwargs))


@pytest.fixture
def logger() -> SpyLogger:
    return SpyLogger()


@pytest.fixture
def working_dir(tmp_path: Path) -> FilesPath:
    root = tmp_path / "work"
    for folder in (
        root / "inputs" / "data",
        root / "inputs" / "trade",
        root / "results",
        root / "qml_updater",
        root / "backtest",
    ):
        folder.mkdir(parents=True, exist_ok=True)

    (root / "inputs" / "data" / "request.xml").write_text(REQUEST_QML, encoding="utf-8")
    (root / "inputs" / "data" / "instructionset.xml").write_text(INSTRUCTION_SET_QML, encoding="utf-8")
    (root / "inputs" / "data" / "MODEL_304_48_172_SNE.xml").write_text(MARKET_DATA_QML, encoding="utf-8")
    (root / "inputs" / "data" / "result.xml").write_text(PRICE_RESULT_QML, encoding="utf-8")
    (root / "inputs" / "data" / "stress.xml").write_text("<stress><name>S</name></stress>", encoding="utf-8")
    (root / "inputs" / "data" / "cache.txt").write_text("ignored", encoding="utf-8")
    (root / "inputs" / "trade" / "price-28405308-product.xml").write_text(PRODUCT_QML, encoding="utf-8")
    (root / "inputs" / "trade" / "price-28405308-pricingparam.xml").write_text(
        PRICING_PARAMS_QML,
        encoding="utf-8",
    )
    return FilesPath(working_dir=str(root))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings.model_validate(
        {
            "pyrds_api": {
                "host": "127.0.0.1",
                "port": 8000,
                "env": "preprod",
                "pyrds_dir": str(tmp_path),
            },
            "environment": {"preprod": "https://preprod.example"},
            "proxies": {"http": "", "https": ""},
            "couch_base_api": {
                "port": 5202,
                "authentication": {
                    "type": "token_based",
                    "token": {"preprod": "token"},
                },
            },
            "ps_api": {"port": 5202},
            "psweb_api": {"port": 4100},
            "market_data_api": {"port": 9003},
            "trade_api": {"port": 5112},
        }
    ).with_api_defaults()


@pytest.fixture
def ps_request() -> SimpleNamespace:
    return SimpleNamespace(valuationDate="2024/01/02 23:59:59")
