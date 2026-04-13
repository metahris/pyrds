from __future__ import annotations

import pytest

from pyrds.domain.stress_models import build_stress_request, generate_iter_values


def test_generate_iter_values() -> None:
    assert generate_iter_values(start=-5, delta=0.1, nbr_points=3) == [-5, -4.9, -4.8]


def test_build_stress_request_creates_cartesian_product() -> None:
    stress_request = build_stress_request(
        {
            "stress_name": "BERM_STRESS",
            "deformations": {
                "rates": {
                    "name": "RateLevel",
                    "mult": {"type": "iter", "start": -5, "delta": 0.1, "nbr_points": 2},
                    "add": {"type": "scalar", "value": 0},
                },
                "vol": {
                    "name": "SigmaShock",
                    "mult": {"type": "vector", "values": [-10, 0, 10]},
                    "add": {"type": "scalar", "value": 0},
                },
            },
        }
    )

    stress = stress_request.stresses[0]
    assert stress.name == "BERM_STRESS"
    assert len(stress.vectorAffineDeformations) == 6
    assert [item.deformation for item in stress.vectorAffineDeformations[0].affineDeformations] == [
        "RateLevel",
        "SigmaShock",
    ]


def test_build_stress_request_rejects_unknown_factor_type() -> None:
    with pytest.raises(ValueError):
        build_stress_request(
            {
                "stress_name": "BAD",
                "deformations": {
                    "rates": {
                        "name": "RateLevel",
                        "mult": {"type": "range"},
                    }
                },
            }
        )
