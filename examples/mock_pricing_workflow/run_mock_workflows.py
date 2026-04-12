from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mock_runtime import (  # noqa: E402
    MockFilesPath,
    MockLogger,
    MockMarketDataApi,
    MockPsApi,
    MockQmlHandler,
    MockTradesApi,
)
from pyrds.application.dto.pricing import FullQmlPricingInput, SimplePricingInput  # noqa: E402
from pyrds.application.runners.full_qml_pricing_runner import FullQmlPricingRunner  # noqa: E402
from pyrds.application.runners.generic_runner import GenericRunner  # noqa: E402
from pyrds.application.runners.simple_pricing_runner import SimplePricingRunner  # noqa: E402
from pyrds.domain.ps_request import GridPricerTechnicalDetails, PsRequest, UseCache  # noqa: E402


def build_ps_request(request_id: str) -> PsRequest:
    return PsRequest(
        requestId=request_id,
        valuationDate="2026-04-12",
        lagInDaysForBackprice=0,
        gridPricerTechnicalDetails=GridPricerTechnicalDetails(
            qmlRunner="MockQmlRunner",
            cartography="MOCK_CARTO",
            foCluster="MOCK_CLUSTER",
            outputCurrency="EUR",
        ),
    )


async def main() -> None:
    base_dir = Path(__file__).resolve().parent
    files_path = MockFilesPath(working_dir=str(base_dir / "workdir"))
    qml_handler = MockQmlHandler()
    logger = MockLogger()
    market_api = MockMarketDataApi()
    trades_api = MockTradesApi()
    ps_api = MockPsApi()

    generic_runner = GenericRunner(
        logger=logger,
        files_path=files_path,
        qml_handler=qml_handler,
        ps_api=ps_api,
        market_api=market_api,
        trades_api=trades_api,
        request_set_tags={"request", "instructionset"},
    )

    ot_raw = generic_runner.compute_ot(build_ps_request("MOCK-OT-001"), dump=False)
    full_raw = generic_runner.compute_full_qml(
        build_ps_request("MOCK-FULL-001"),
        use_cache_factory=UseCache,
        dump=False,
    )
    custom_raw = generic_runner.compute_custom_mkt_data(
        build_ps_request("MOCK-CUSTOM-MKT-001"),
        use_cache_factory=UseCache,
        dump=False,
    )

    simple_runner = SimplePricingRunner(
        market_data_port=market_api,
        trades_port=trades_api,
        pricing_port=ps_api,
    )
    simple_result = simple_runner.run(
        SimplePricingInput(
            request_id="MOCK-SIMPLE-001",
            ps_request=build_ps_request("MOCK-SIMPLE-001"),
            trade_id="MOCK-TRADE-001",
            product_qml=(base_dir / "workdir" / "inputs" / "trade" / "product.xml").read_text(),
            pricing_parameters_qml=(
                base_dir / "workdir" / "inputs" / "trade" / "pricingparams.xml"
            ).read_text(),
            market_data={
                "EUR|BASE": (base_dir / "workdir" / "inputs" / "data" / "eur-curve.xml").read_text()
            },
        )
    )

    full_qml_runner = FullQmlPricingRunner(pricing_port=ps_api)
    full_qml_result = full_qml_runner.run(
        FullQmlPricingInput(
            runner="MockQmlRunner",
            instruction_set_qml=(
                base_dir / "workdir" / "inputs" / "data" / "instructionset.xml"
            ).read_text(),
            request_qml=(base_dir / "workdir" / "inputs" / "data" / "request.xml").read_text(),
        )
    )

    batch_response = await ps_api.price_async(
        [
            build_ps_request("MOCK-BATCH-001").model_dump(by_alias=True, exclude_none=True),
            build_ps_request("MOCK-BATCH-002").model_dump(by_alias=True, exclude_none=True),
        ]
    )

    print("\nMock workflow outputs")
    print(f"OT raw keys: {list(ot_raw.keys())}")
    print(f"Full QML raw keys: {list(full_raw.keys())}")
    print(f"Custom market data raw keys: {list(custom_raw.keys())}")
    print(f"Simple pricing workflow: {simple_result.workflow}")
    print(f"Full QML request set: {full_qml_result.context.request_set_id}")
    print(f"Batch response keys: {list(batch_response.keys())}")
    print(f"Market data sets created: {list(market_api.sets.keys())}")
    print(f"Trade sets created: {list(trades_api.sets.keys())}")
    print(f"Request sets created: {list(ps_api.request_sets.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
