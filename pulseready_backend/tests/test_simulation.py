import concurrent.futures

import pytest
from pydantic import ValidationError

from app.simulation.service import run_capacity_simulation


def scenario(**overrides):
    values = {
        "staffed_beds": 80,
        "total_beds": 100,
        "baseline_demand_beds": 70,
        "demand_uplift_pct": 10,
        "absenteeism_pct": 25,
        "horizon_hours": 24,
        "seed": 7,
    }
    values.update(overrides)
    return values


def test_same_inputs_and_seed_are_identical_and_input_changes_result():
    first = run_capacity_simulation(**scenario()).model_dump()
    second = run_capacity_simulation(**scenario()).model_dump()
    changed = run_capacity_simulation(**scenario(demand_uplift_pct=20)).model_dump()
    assert first == second
    assert first["projected_demand_beds"] != changed["projected_demand_beds"]


def test_zero_capacity_is_explicit_and_serializable():
    result = run_capacity_simulation(**scenario(staffed_beds=0)).model_dump()
    assert result["simulated_staffed_beds"] == 0
    assert result["shortfall_beds"] == 77
    assert result["capacity_utilization_pct"] is None


@pytest.mark.parametrize("overrides", [
    {"staffed_beds": 101},
    {"horizon_hours": 169},
    {"demand_uplift_pct": -1},
])
def test_invalid_values_are_rejected(overrides):
    with pytest.raises(ValidationError):
        run_capacity_simulation(**scenario(**overrides))


def test_concurrent_runs_do_not_share_mutable_state():
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: run_capacity_simulation(**scenario()).model_dump(), range(8)))
    assert all(result == results[0] for result in results)
