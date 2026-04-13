from __future__ import annotations

from itertools import product
from typing import Any

from pydantic import Field

from pyrds.domain.models import CustomBaseModel


class StressFactors(CustomBaseModel):
    add: float = 0.0
    mult: float = 1.0


class StressAffineDeformation(CustomBaseModel):
    deformation: str
    factors: StressFactors


class StressAffineDeformations(CustomBaseModel):
    affineDeformations: list[StressAffineDeformation] = Field(default_factory=list)


class Stress(CustomBaseModel):
    name: str
    vectorAffineDeformations: list[StressAffineDeformations] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StressField(Stress):
    """Backward-compatible name for the previous simple stress field model."""


class StressRequest(CustomBaseModel):
    stresses: list[Stress]
    metadata: dict[str, Any] = Field(default_factory=dict)


def generate_iter_values(start: float, delta: float, nbr_points: int) -> list[float]:
    return [start + i * delta for i in range(nbr_points)]


def build_stress_request(data: dict[str, Any]) -> StressRequest:
    """Build the runner stress model from the compact API/example stress shape."""
    stress_name = str(data["stress_name"])
    deformations_data = data.get("deformations") or {}
    if not deformations_data:
        raise ValueError("stress.deformations must contain at least one deformation.")

    deformation_options: list[list[StressAffineDeformation]] = []
    for fallback_name, deformation_data in deformations_data.items():
        deformation_name = str(deformation_data.get("name") or fallback_name)
        mult_values = _resolve_factor_values(
            deformation_data.get("mult") or {"type": "scalar", "value": 1.0}
        )
        add_values = _resolve_factor_values(
            deformation_data.get("add") or {"type": "scalar", "value": 0.0}
        )

        deformation_options.append(
            [
                StressAffineDeformation(
                    deformation=deformation_name,
                    factors=StressFactors(mult=float(mult), add=float(add)),
                )
                for mult in mult_values
                for add in add_values
            ]
        )

    vector_affine_deformations = [
        StressAffineDeformations(affineDeformations=list(combo))
        for combo in product(*deformation_options)
    ]

    return StressRequest(
        stresses=[
            Stress(
                name=stress_name,
                vectorAffineDeformations=vector_affine_deformations,
            )
        ]
    )


def _resolve_factor_values(spec: dict[str, Any]) -> list[float]:
    spec_type = spec.get("type")
    if spec_type == "iter":
        return generate_iter_values(
            start=float(spec["start"]),
            delta=float(spec["delta"]),
            nbr_points=int(spec["nbr_points"]),
        )
    if spec_type == "scalar":
        return [float(spec["value"])]
    if spec_type == "vector":
        return [float(value) for value in spec["values"]]
    raise ValueError(f"Unsupported stress factor type: {spec_type}")
