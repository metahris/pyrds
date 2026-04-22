from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from pyrds.infrastructure.config.settings import Settings
from pyrds.sdk.client import PyrdsClient


MARKET_DATA_QML = """
<yieldcurve>
  <name>SDK_TEST_CURVE</name>
  <currency>USD</currency>
</yieldcurve>
""".strip()

PRODUCT_QML = """
<product>
  <name>SDK_TEST_TRADE</name>
  <notional>1</notional>
</product>
""".strip()

PRICING_PARAMS_QML = """
<pricingparams>
  <method>BASE</method>
</pricingparams>
""".strip()

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
</request>
""".strip()

INSTRUCTION_SET_QML = """
<instructionset>
  <name>SDK_TEST_INSTRUCTIONSET</name>
  <instructions count="1">
    <item type="PRICE" version="8">
      <valdate>2024/06/26</valdate>
      <refccy alloutputs="0">USD</refccy>
      <aggregatedccy>NONE</aggregatedccy>
      <mktdataenv>BASE</mktdataenv>
      <output>
        <count>1</count>
        <item>PresentValue</item>
      </output>
      <outputParams/>
      <shiftscenario/>
    </item>
  </instructions>
</instructionset>
""".strip()


def _load_settings(pytestconfig: pytest.Config) -> Settings:
    config_path = pytestconfig.getoption("--e2e-config")
    return Settings.load(config_path) if config_path else Settings.load()


def _load_qml_runner() -> str:
    payload_path = Path("examples/api_payloads/generic_ot_id.json")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    return str(payload["ps_request"]["gridPricerTechnicalDetails"]["qmlRunner"])


def _extract_qml_text(payload: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            text = value.get("text")
            if isinstance(text, str):
                return text
    return None


@pytest.mark.e2e
def test_real_market_data_set_round_trip(pytestconfig: pytest.Config) -> None:
    settings = _load_settings(pytestconfig)
    qml_runner = _load_qml_runner()
    market_data_key = f"SDK_TEST_CURVE_{uuid4().hex[:12]}|BASE"

    client = PyrdsClient(settings=settings)
    try:
        params = client.market_data_api.build_set_access_params(qml_runner=qml_runner)
        set_id = client.market_data_api.create_set(params=params)
        client.market_data_api.add_qml(
            set_id=set_id,
            market_data_id=market_data_key,
            market_data_qml=MARKET_DATA_QML,
            params=params,
        )

        keys = client.market_data_api.get_mkt_data_keys(set_id=set_id, params=params)
        content = client.market_data_api.get_mkt_data_content(
            set_id=set_id,
            key=market_data_key,
            params=params,
        )
        async_content = asyncio.run(
            client.market_data_api.get_mkt_data_content_async(
                set_id=set_id,
                key=market_data_key,
                params=params,
            )
        )
    finally:
        client.close()

    assert market_data_key in [str(key) for key in keys]
    assert content == MARKET_DATA_QML
    assert async_content == MARKET_DATA_QML


@pytest.mark.e2e
def test_real_trade_set_round_trip(pytestconfig: pytest.Config) -> None:
    settings = _load_settings(pytestconfig)
    qml_runner = _load_qml_runner()
    trade_id = f"SDK_TEST_TRADE_{uuid4().hex[:12]}"

    client = PyrdsClient(settings=settings)
    try:
        params = client.trades_api.build_set_access_params(qml_runner=qml_runner)
        set_id = client.trades_api.create_set(params=params)
        client.trades_api.add_qml(
            set_id=set_id,
            trade_id=trade_id,
            product_qml=PRODUCT_QML,
            pricing_parameters_qml=PRICING_PARAMS_QML,
            params=params,
        )

        trade_ids = client.trades_api.get_trades_in_set(set_id=set_id, params=params)
        trade_content = client.trades_api.get_trade_content(
            set_id=set_id,
            trade_id=trade_id,
            params=params,
        )
        async_trade_ids = asyncio.run(client.trades_api.get_trades_in_set_async(set_id=set_id, params=params))
        async_trade_content = asyncio.run(
            client.trades_api.get_trade_content_async(
                set_id=set_id,
                trade_id=trade_id,
                params=params,
            )
        )
    finally:
        client.close()

    product_qml = _extract_qml_text(trade_content, "qml_product", "productQml", "product_qml")
    pricing_qml = _extract_qml_text(
        trade_content,
        "qml_pricing_params",
        "pricingParamsQml",
        "pricing_params_qml",
    )
    async_product_qml = _extract_qml_text(async_trade_content, "qml_product", "productQml", "product_qml")
    async_pricing_qml = _extract_qml_text(
        async_trade_content,
        "qml_pricing_params",
        "pricingParamsQml",
        "pricing_params_qml",
    )

    assert trade_id in [str(item) for item in trade_ids]
    assert trade_id in [str(item) for item in async_trade_ids]
    assert product_qml == PRODUCT_QML
    assert pricing_qml == PRICING_PARAMS_QML
    assert async_product_qml == PRODUCT_QML
    assert async_pricing_qml == PRICING_PARAMS_QML


@pytest.mark.e2e
def test_real_request_set_create_and_add_qml(pytestconfig: pytest.Config) -> None:
    settings = _load_settings(pytestconfig)
    qml_runner = _load_qml_runner()

    client = PyrdsClient(settings=settings)
    try:
        set_id = client.pricing_api.create_set(qml_runner=qml_runner)
        returned_id = client.pricing_api.add_qml(
            set_id=set_id,
            instruction_set_qml=INSTRUCTION_SET_QML,
            request_qml=REQUEST_QML,
            qml_runner=qml_runner,
        )
    finally:
        client.close()

    assert returned_id == set_id
