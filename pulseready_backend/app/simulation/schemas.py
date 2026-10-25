from pydantic import BaseModel, ConfigDict, Field, model_validator


class CapacitySimulationRequest(BaseModel):
    """Explicit, hypothetical inputs for the bounded capacity model."""

    model_config = ConfigDict(extra="forbid")

    staffed_beds: int = Field(ge=0, le=1_000_000)
    total_beds: int = Field(ge=0, le=1_000_000)
    baseline_demand_beds: int = Field(ge=0, le=1_000_000)
    demand_uplift_pct: float = Field(ge=0, le=500)
    absenteeism_pct: float = Field(ge=0, le=100)
    horizon_hours: int = Field(default=1, ge=1, le=168)
    seed: int = Field(default=0, ge=0, le=2**32 - 1)

    @model_validator(mode="after")
    def beds_are_consistent(self):
        if self.staffed_beds > self.total_beds:
            raise ValueError("staffed_beds cannot exceed total_beds")
        return self


class CapacitySimulationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_version: str
    seed: int
    horizon_hours: int
    simulated_staffed_beds: int
    projected_demand_beds: int
    shortfall_beds: int
    capacity_utilization_pct: float | None
