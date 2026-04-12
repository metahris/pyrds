from __future__ import annotations

from fastapi import APIRouter, Depends

from pyrds.api.dependencies import get_client
from pyrds.api.schemas import (
    BatchPricingRequest,
    FullQmlPricingRequest,
    PricingResponse,
    SimplePricingRequest,
)
from pyrds.api.static_loader import load_api_examples
from pyrds.application.dto.pricing import BatchPricingInput, FullQmlPricingInput, SimplePricingInput
from pyrds.sdk.client import PyrdsClient

api_examples = load_api_examples().get("pricing", {})
router = APIRouter(prefix="/pricing", tags=["Pricing"])


@router.post(
    "/simple",
    response_model=PricingResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {"simple": api_examples.get("simple", {})}
                }
            }
        }
    },
)
def price_simple(
    request: SimplePricingRequest,
    client: PyrdsClient = Depends(get_client),
) -> PricingResponse:
    result = client.price_simple(SimplePricingInput.model_validate(request.model_dump(by_alias=True)))
    return PricingResponse.model_validate(result.model_dump())


@router.post(
    "/full-qml",
    response_model=PricingResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {"full_qml": api_examples.get("full_qml", {})}
                }
            }
        }
    },
)
def price_full_qml(
    request: FullQmlPricingRequest,
    client: PyrdsClient = Depends(get_client),
) -> PricingResponse:
    result = client.price_full_qml(FullQmlPricingInput.model_validate(request.model_dump(by_alias=True)))
    return PricingResponse.model_validate(result.model_dump())


@router.post(
    "/batch",
    response_model=PricingResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {"batch": api_examples.get("batch", {})}
                }
            }
        }
    },
)
async def price_batch(
    request: BatchPricingRequest,
    client: PyrdsClient = Depends(get_client),
) -> PricingResponse:
    result = await client.price_batch(BatchPricingInput.model_validate(request.model_dump(by_alias=True)))
    return PricingResponse.model_validate(result.model_dump())
