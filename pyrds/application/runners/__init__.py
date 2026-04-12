from __future__ import annotations

from typing import Any

__all__ = [
    "Backtester",
    "BaseRunner",
    "FullQmlPricingRunner",
    "GenericRunner",
    "HybridRunner",
    "OverrideQmlRunner",
    "OverrideQmlsRunner",
    "QlibReqValidator",
    "SimplePricingRunner",
    "StressRunner",
]

_RUNNER_IMPORTS = {
    "Backtester": "pyrds.application.runners.backtester",
    "BaseRunner": "pyrds.application.runners.base_runner",
    "FullQmlPricingRunner": "pyrds.application.runners.full_qml_pricing_runner",
    "GenericRunner": "pyrds.application.runners.generic_runner",
    "HybridRunner": "pyrds.application.runners.hybrid_runner",
    "OverrideQmlRunner": "pyrds.application.runners.override_qml_runner",
    "OverrideQmlsRunner": "pyrds.application.runners.override_qmls_runner",
    "QlibReqValidator": "pyrds.application.runners.qlib_req_validator",
    "SimplePricingRunner": "pyrds.application.runners.simple_pricing_runner",
    "StressRunner": "pyrds.application.runners.stress_runner",
}


def __getattr__(name: str) -> Any:
    if name not in _RUNNER_IMPORTS:
        raise AttributeError(name)

    from importlib import import_module

    module = import_module(_RUNNER_IMPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
