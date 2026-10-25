import simpy

from app.simulation.model import MODEL_VERSION, capacity_snapshot_process
from app.simulation.schemas import CapacitySimulationRequest, CapacitySimulationResult


def run_simulation(request: CapacitySimulationRequest) -> CapacitySimulationResult:
    """Run a fresh, bounded environment and return a serializable summary."""
    environment = simpy.Environment()
    result: dict = {}
    environment.process(capacity_snapshot_process(environment, request, result))
    environment.run(until=min(float(request.horizon_hours), 1.0))
    if not result:
        raise RuntimeError("simulation did not complete within the configured horizon")
    return CapacitySimulationResult(
        model_version=MODEL_VERSION,
        seed=request.seed,
        horizon_hours=request.horizon_hours,
        **result,
    )
