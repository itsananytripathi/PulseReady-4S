"""Pure hospital capacity process definitions for the bounded SimPy model."""

import math
import simpy

from app.simulation.schemas import CapacitySimulationRequest


MODEL_VERSION = "capacity-simpy-v1"


def effective_capacity(request: CapacitySimulationRequest) -> int:
    return max(
        0,
        min(
            request.total_beds,
            math.floor(request.staffed_beds * (1 - request.absenteeism_pct / 100.0)),
        ),
    )


def projected_demand(request: CapacitySimulationRequest) -> int:
    return math.ceil(request.baseline_demand_beds * (1 + request.demand_uplift_pct / 100.0))


def capacity_snapshot_process(env: simpy.Environment, request: CapacitySimulationRequest, result: dict):
    """Evaluate one bounded snapshot through a fresh SimPy environment.

    This model intentionally does not simulate patient-level clinical care. A
    single zero-duration request represents the capacity snapshot; the
    horizon and seed are still explicit metadata so future process detail can
    be added without sharing live application state.
    """
    capacity = effective_capacity(request)
    resource = simpy.Resource(env, capacity=max(1, capacity))
    request_token = resource.request()
    yield request_token
    demand = projected_demand(request)
    result.update({
        "simulated_staffed_beds": capacity,
        "projected_demand_beds": demand,
        "shortfall_beds": max(0, demand - capacity),
        "capacity_utilization_pct": None if capacity == 0 else round(100.0 * demand / capacity, 2),
    })
    resource.release(request_token)
