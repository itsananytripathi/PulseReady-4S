from __future__ import annotations
import math
import pandas as pd

def rolling_baseline_anomalies(
    frame: pd.DataFrame,
    *,
    value_col: str = "value",
    time_col: str = "observed_at",
    window: int = 7,
    min_periods: int = 4,
    z_threshold: float = 3.0,
) -> pd.DataFrame:
    """
    Deterministic rolling z-score using PRIOR observations only.
    Input must be one facility + one signal_type series, sorted internally by time.
    A zero/near-zero historical standard deviation uses an absolute deviation check:
    any positive deviation from a constant baseline is flagged only if it exceeds
    max(1.0, 3 * sqrt(max(baseline_mean, 1))). Tune this rule in pilots.
    """
    if window < 2 or min_periods < 2 or min_periods > window:
        raise ValueError("Require window >= min_periods >= 2")
    if value_col not in frame or time_col not in frame:
        raise ValueError(f"frame must contain {value_col!r} and {time_col!r}")
    out = frame.copy()
    out[time_col] = pd.to_datetime(out[time_col], utc=True, errors="raise")
    out = out.sort_values(time_col).reset_index(drop=True)
    values = pd.to_numeric(out[value_col], errors="raise").astype(float)
    prior = values.shift(1)
    mean = prior.rolling(window=window, min_periods=min_periods).mean()
    std = prior.rolling(window=window, min_periods=min_periods).std(ddof=0)
    scores = []
    flags = []
    for v, m, s in zip(values, mean, std):
        if pd.isna(m) or pd.isna(s):
            scores.append(None); flags.append(False); continue
        if s > 1e-9:
            score = (v - m) / s
            scores.append(float(score))
            flags.append(bool(score >= z_threshold))
        else:
            threshold = max(1.0, 3.0 * math.sqrt(max(float(m), 1.0)))
            deviation = v - float(m)
            scores.append(float(deviation / threshold))
            flags.append(bool(deviation > threshold))
    out["baseline_mean"] = mean
    out["baseline_std"] = std
    out["anomaly_score"] = scores
    out["is_anomaly"] = flags
    return out

def calculate_4s_readiness(
    *, staff_available: int, staff_required: int,
    supply_on_hand: float, daily_supply_consumption: float,
    staffed_beds: int, total_beds: int, system_status_score: float
) -> dict:
    """Transparent v1 heuristic. All dimension scores are bounded 0..100."""
    def ratio_score(numerator: float, denominator: float) -> float:
        if denominator <= 0:
            return 100.0 if numerator >= 0 else 0.0
        return round(max(0.0, min(100.0, 100.0 * numerator / denominator)), 2)
    staff = ratio_score(staff_available, staff_required)
    stuff = 100.0 if daily_supply_consumption <= 0 else round(
        max(0.0, min(100.0, 100.0 * supply_on_hand / (daily_supply_consumption * 7.0))), 2
    )
    space = ratio_score(staffed_beds, total_beds)
    system = round(max(0.0, min(100.0, system_status_score)), 2)
    # Equal-weight mean is a transparent prototype choice, not a validated clinical score.
    overall = round((staff + stuff + space + system) / 4.0, 2)
    buffer_days = None if daily_supply_consumption <= 0 else round(supply_on_hand / daily_supply_consumption, 2)
    return {
        "staff_score": staff, "stuff_score": stuff, "space_score": space,
        "system_score": system, "overall_score": overall,
        "supply_buffer_days": buffer_days,
        "supply_status": (
            "unknown" if buffer_days is None else
            "critical" if buffer_days < 2 else
            "low" if buffer_days < 5 else "adequate"
        )
    }

def simulate_capacity(
    *, staffed_beds: int, total_beds: int,
    baseline_demand_beds: int, demand_uplift_pct: float,
    absenteeism_pct: float
) -> dict:
    """Integer, deterministic what-if arithmetic; not a forecast."""
    effective_beds = max(0, min(total_beds, math.floor(staffed_beds * (1 - absenteeism_pct / 100.0))))
    projected_demand = math.ceil(baseline_demand_beds * (1 + demand_uplift_pct / 100.0))
    shortfall = max(0, projected_demand - effective_beds)
    utilization = None if effective_beds == 0 else round(100.0 * projected_demand / effective_beds, 2)
    return {
        "simulated_staffed_beds": effective_beds,
        "projected_demand_beds": projected_demand,
        "shortfall_beds": shortfall,
        "capacity_utilization_pct": utilization
    }
