from app.simulation.runner import run_simulation
from app.simulation.schemas import CapacitySimulationRequest, CapacitySimulationResult


def run_capacity_simulation(**inputs) -> CapacitySimulationResult:
    """Validate and execute an isolated capacity scenario."""
    request = CapacitySimulationRequest(**inputs)
    return run_simulation(request)
