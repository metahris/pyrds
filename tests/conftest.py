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
<request version="3">
  <product>!{PRODUCT}</product>
  <instruction/>
  <instructionset>!{INSTRUCTIONSET}</instructionset>
  <pricingparam>!{PRICINGPARAM}</pricingparam>
  <setups version="1">
    <yieldcurve>YCSETUP</yieldcurve>
    <volatility>VOLIRSETUP</volatility>
    <credit>CCSETUP</credit>
    <rootMktData/>
  </setups>
  <displayResult>true</displayResult>
  <gridConfiguration>
    <depth>0</depth>
    <maxDepth>0</maxDepth>
    <timeLimit>0</timeLimit>
    <minSubTasksToSerial>0</minSubTasksToSerial>
    <distribute>true</distribute>
    <verbose>false</verbose>
  </gridConfiguration>
  <qlibCacheClearing>PARTIAL</qlibCacheClearing>
  <debug>false</debug>
</request>
"""

INSTRUCTION_SET_QML = """
<instructionset>
  <name>28405308-28405306-EventLeg-SNE-2023-10-09-12-01-50</name>
  <instructions count="2">
    <item type="PRICE" version="8">
      <valdate>2024/06/26</valdate>
      <refccy alloutputs="0">USD</refccy>
      <aggregatedccy>NONE</aggregatedccy>
      <filterDateCCF>2024/06/26</filterDateCCF>
      <mktdataenv>BASE</mktdataenv>
      <validateCF>false</validateCF>
      <filterCF>NONE</filterCF>
      <additionalprices>
        <count>3</count>
        <item>Underlying</item>
        <item>Option</item>
        <item>CreditEvent</item>
      </additionalprices>
      <output>
        <count>4</count>
        <item>PresentValue</item>
        <item>ExerciseCost</item>
        <item>Spot</item>
        <item>FixFees</item>
      </output>
      <outputParams/>
      <shiftscenario/>
    </item>
    <item type="DELTAIR" version="6">
      <base version="9">
        <shiftType>CUMUL_UP</shiftType>
        <incType>CENTRED</incType>
        <shiftValue type="STANDARD">
          <value>2</value>
        </shiftValue>
        <calibrationparams>
          <calibration>CALIBRATE</calibration>
        </calibrationparams>
      </base>
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
<model type="EPLGM2Bridge" version="17">
  <numericalMethod>EDP</numericalMethod>
  <nbTotalSimul>10000</nbTotalSimul>
  <nbSimul>10000</nbSimul>
  <regressionDegree>2</regressionDegree>
  <nstept>10</nstept>
  <advancedSettings version="2">
    <toleranceNotio>0.01</toleranceNotio>
  </advancedSettings>
  <calibset>
    <count>1</count>
    <item>
      <key>USD</key>
      <val>CALIBRATOR_304_USD</val>
    </item>
  </calibset>
  <domesticCurrency>USD</domesticCurrency>
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

    def contains(self, text: str) -> bool:
        return any(text in str(args) for _, args, _ in self.messages)


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

    (root / "inputs" / "data" / "120482_BASE.xml").write_text("<yieldcurve><id>120482</id></yieldcurve>", encoding="utf-8")
    (root / "inputs" / "data" / "123778_BASE.xml").write_text("<yieldcurve><id>123778</id></yieldcurve>", encoding="utf-8")
    (root / "inputs" / "data" / "CALIBRATOR_304_USD_BASE.xml").write_text(
        "<calibrator type=\"ECONOMY\"><maxIter>400</maxIter></calibrator>",
        encoding="utf-8",
    )
    (root / "inputs" / "data" / "MODEL_304_48_172_BASE.xml").write_text(MARKET_DATA_QML, encoding="utf-8")
    (root / "inputs" / "data" / "VOL_IR_USD_BASE.xml").write_text("<volatility><currency>USD</currency></volatility>", encoding="utf-8")
    (root / "inputs" / "data" / "VOLIRSETUP_BASE.xml").write_text("<volirsetup><name>VOLIRSETUP</name></volirsetup>", encoding="utf-8")
    (root / "inputs" / "data" / "YCSETUP_BASE.xml").write_text("<ycsetup><name>YCSETUP</name></ycsetup>", encoding="utf-8")
    (root / "inputs" / "data" / "price-28405308-request.xml").write_text(REQUEST_QML, encoding="utf-8")
    (root / "inputs" / "data" / "price-28405308-instructionset.xml").write_text(INSTRUCTION_SET_QML, encoding="utf-8")
    (root / "inputs" / "data" / "price-28405308-executeresult.xml").write_text(PRICE_RESULT_QML, encoding="utf-8")
    (root / "inputs" / "data" / "static_data.xml").write_text("<staticData><enabled>true</enabled></staticData>", encoding="utf-8")
    (root / "inputs" / "data" / "BERM_STRESS.xml").write_text(
        "<stress><name>BERM_STRESS</name></stress>",
        encoding="utf-8",
    )
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
    return SimpleNamespace(valuationDate="2024/06/26 23:59:59")
