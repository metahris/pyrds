from __future__ import annotations

from lxml import etree
import pytest

from pyrds.application.services.qml_override_service import QmlOverrideService
from pyrds.domain.exceptions import OverrideApplicationError, OverrideValidationError
from pyrds.domain.override_models import OverridePlan, OverrideScenario, OverrideTargetType
from tests.conftest import PRICING_PARAMS_QML


def _text(xml: str, xpath: str) -> str | None:
    nodes = etree.fromstring(xml.encode("utf-8")).xpath(xpath)
    if not nodes:
        return None
    node = nodes[0]
    if isinstance(node, etree._Element):
        return node.text
    return str(node)


def test_replace_file_apply_to_all_targets(working_dir, logger) -> None:
    service = QmlOverrideService(files_path=working_dir, logger=logger)
    scenario = OverrideScenario.model_validate(
        {
            "scenario_id": "same_ppm_all_trades",
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

    result = service.apply_scenario_to_mapping(
        qml_by_target_id={
            "trade_1": PRICING_PARAMS_QML,
            "trade_2": PRICING_PARAMS_QML,
        },
        scenario=scenario,
        target_type=OverrideTargetType.PRICINGPARAMS,
    )

    assert _text(result["trade_1"], "./method") == "NEW"
    assert _text(result["trade_2"], "./method") == "NEW"


def test_replace_file_per_target_source(working_dir, logger) -> None:
    service = QmlOverrideService(files_path=working_dir, logger=logger)
    scenario = OverrideScenario.model_validate(
        {
            "scenario_id": "per_trade_ppm",
            "overrides": [
                {
                    "name": "replace_pricingparams_by_trade",
                    "target_type": "pricingparams",
                    "operation": "replace_file",
                    "target_sources": [
                        {
                            "target_id": "trade_1",
                            "source": {"inline_xml": "<pricingparams><method>A</method></pricingparams>"},
                        },
                        {
                            "target_id": "trade_2",
                            "source": {"inline_xml": "<pricingparams><method>B</method></pricingparams>"},
                        },
                    ],
                }
            ],
        }
    )

    result = service.apply_scenario_to_mapping(
        qml_by_target_id={
            "trade_1": PRICING_PARAMS_QML,
            "trade_2": PRICING_PARAMS_QML,
        },
        scenario=scenario,
        target_type=OverrideTargetType.PRICINGPARAMS,
    )

    assert _text(result["trade_1"], "./method") == "A"
    assert _text(result["trade_2"], "./method") == "B"


def test_replace_block_updates_first_matching_tag(working_dir, logger) -> None:
    service = QmlOverrideService(files_path=working_dir, logger=logger)

    result = service.replace_block(
        qml="<model><curve><rate>1.0</rate></curve></model>",
        block_xml="<curve><rate>2.0</rate></curve>",
    )

    assert _text(result, "./curve/rate") == "2.0"


def test_replace_blocks_rejects_duplicate_tags(working_dir, logger) -> None:
    service = QmlOverrideService(files_path=working_dir, logger=logger)

    with pytest.raises(OverrideValidationError):
        service.replace_blocks(
            qml="<pricingparams><method>BASE</method></pricingparams>",
            blocks_xml=["<method>A</method>", "<method>B</method>"],
        )


def test_set_xpath_text_and_attribute(working_dir, logger) -> None:
    service = QmlOverrideService(files_path=working_dir, logger=logger)

    updated = service.set_xpath_text(
        qml=PRICING_PARAMS_QML,
        xpath="./method",
        value="ALT",
    )
    updated = service.set_xpath_attribute(
        qml=updated,
        xpath="./flag",
        attribute="enabled",
        value="true",
    )

    root = etree.fromstring(updated.encode("utf-8"))
    assert root.xpath("string(./method)") == "ALT"
    assert root.xpath("string(./flag/@enabled)") == "true"


def test_xpath_exactly_one_policy_raises_on_multiple_matches(working_dir, logger) -> None:
    service = QmlOverrideService(files_path=working_dir, logger=logger)

    with pytest.raises(OverrideApplicationError):
        service.set_xpath_text(
            qml="<root><item>1</item><item>2</item></root>",
            xpath="./item",
            value="3",
        )


def test_override_plan_rejects_duplicate_scenario_ids() -> None:
    with pytest.raises(OverrideValidationError):
        OverridePlan.model_validate(
            {
                "scenarios": [
                    {"scenario_id": "same", "overrides": []},
                    {"scenario_id": "same", "overrides": []},
                ]
            }
        )
