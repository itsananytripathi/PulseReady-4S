import pandas as pd
from app.analytics import calculate_4s_readiness, simulate_capacity, rolling_baseline_anomalies

def test_readiness_and_buffer():
    result = calculate_4s_readiness(
        staff_available=8, staff_required=10, supply_on_hand=300,
        daily_supply_consumption=100, staffed_beds=50, total_beds=100,
        system_status_score=80
    )
    assert result["staff_score"] == 80
    assert result["supply_buffer_days"] == 3
    assert result["supply_status"] == "low"
    assert 0 <= result["overall_score"] <= 100

def test_simulation_is_deterministic():
    kwargs = dict(staffed_beds=80, total_beds=100, baseline_demand_beds=60,
                  demand_uplift_pct=25, absenteeism_pct=10)
    assert simulate_capacity(**kwargs) == simulate_capacity(**kwargs)
    assert simulate_capacity(**kwargs)["simulated_staffed_beds"] == 72
    assert simulate_capacity(**kwargs)["projected_demand_beds"] == 75

def test_anomaly_uses_prior_baseline():
    frame = pd.DataFrame({
        "observed_at": pd.date_range("2026-01-01", periods=8, freq="h", tz="UTC"),
        "value": [5, 5, 6, 5, 5, 6, 5, 30]
    })
    result = rolling_baseline_anomalies(frame, window=6, min_periods=4, z_threshold=3)
    assert bool(result.iloc[-1]["is_anomaly"])
