from __future__ import annotations

from pyrds.application.dto.pricing import FullQmlPricingInput
from pyrds.application.ports.pricing import PricingPort
from pyrds.domain.models import PricingExecutionResult, PricingWorkflowContext


class FullQmlPricingRunner:
    def __init__(self, *, pricing_port: PricingPort) -> None:
        self._pricing_port = pricing_port

    def run(self, data: FullQmlPricingInput) -> PricingExecutionResult:
        request_set_id = data.request_set_id or self._pricing_port.create_set(data.runner)
        request_id = self._pricing_port.add_qml(
            set_id=request_set_id,
            instruction_set_qml=data.instruction_set_qml,
            request_qml=data.request_qml,
            qml_runner=data.runner,
        )
        return PricingExecutionResult(
            workflow="full-qml-pricing",
            context=PricingWorkflowContext(request_set_id=request_set_id),
            payload={"requestId": request_id, "runner": data.runner},
            raw_response={"requestId": request_id, "requestSetId": request_set_id},
        )
