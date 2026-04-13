from __future__ import annotations

import json
from pathlib import Path

import pytest

from pyrds.application.services.payload_mapper import model_to_payload
from pyrds.domain.ps_request import PsRequest
from pyrds.infrastructure.config.settings import Settings
from pyrds.sdk.client import PyrdsClient


@pytest.mark.e2e
def test_real_ot_pricing_returns_response(pytestconfig: pytest.Config) -> None:
    payload_path = Path("examples/api_payloads/generic_ot_id.json")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    ps_request = PsRequest.model_validate(payload["ps_request"])

    config_path = pytestconfig.getoption("--e2e-config")
    settings = Settings.load(config_path) if config_path else Settings.load()

    client = PyrdsClient(settings=settings)
    try:
        response = client.pricing_api.price(model_to_payload(ps_request))
    finally:
        client.close()

    assert isinstance(response, dict)
    assert response
