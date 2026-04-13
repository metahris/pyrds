from __future__ import annotations

from types import SimpleNamespace

import pytest

from pyrds.application.runners.base_runner import BaseRunner
from pyrds.domain.exceptions import NonRetryableAPIError, PricingComputationError


class FakePricingApi:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def price(self, body):
        raise self.exc

    async def price_async(self, priceable, fail_on_any_error=False):
        raise self.exc


def _runner(exc: Exception) -> BaseRunner:
    return BaseRunner(
        logger=None,
        files_path=SimpleNamespace(),
        qml_handler=SimpleNamespace(),
        ps_api=FakePricingApi(exc),
        market_api=SimpleNamespace(),
        trades_api=SimpleNamespace(),
    )


def test_compute_preserves_upstream_api_error_details() -> None:
    upstream_error = NonRetryableAPIError(
        "HTTP 400 returned from pricing",
        status_code=400,
        url="https://pricing.example/price",
        response_json={"message": "bad request"},
    )

    with pytest.raises(NonRetryableAPIError) as exc_info:
        _runner(upstream_error)._compute({"requestId": "req"})

    assert exc_info.value.status_code == 400
    assert exc_info.value.url == "https://pricing.example/price"
    assert exc_info.value.response_json == {"message": "bad request"}


def test_compute_wraps_unknown_local_failure_with_cause() -> None:
    with pytest.raises(PricingComputationError) as exc_info:
        _runner(RuntimeError("serializer exploded"))._compute({"requestId": "req"})

    assert str(exc_info.value) == "Synchronous pricing failed: serializer exploded"
