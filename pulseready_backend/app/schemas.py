from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

class IngestSummary(BaseModel):
    accepted_rows: int
    rejected_rows: int
    rejected: list[dict]
    created_signal_ids: list[str]
    alerts_created: int
    note: str = "Signals are operational indicators for human review, not confirmed outbreaks."

class ReadinessOut(BaseModel):
    facility_id: str
    facility_code: str
    facility_name: str
    staff_score: float
    stuff_score: float
    space_score: float
    system_score: float
    overall_score: float
    supply_buffer_days: float | None
    supply_status: Literal["unknown", "critical", "low", "adequate"]
    staffed_beds: int
    total_beds: int

class AlertOut(BaseModel):
    id: str
    facility_id: str
    facility_code: str
    severity: str
    status: str
    title: str
    explanation: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class OverviewOut(BaseModel):
    generated_at: datetime
    readiness: list[ReadinessOut]
    active_alerts: list[AlertOut]

class SimulateRequest(BaseModel):
    facility_code: str = Field(min_length=1, max_length=80)
    demand_uplift_pct: float = Field(default=0, ge=0, le=500)
    absenteeism_pct: float = Field(default=0, ge=0, le=100)
    baseline_demand_beds: int = Field(ge=0, le=100000)

class SimulateResponse(BaseModel):
    simulation_id: str
    facility_code: str
    baseline_staffed_beds: int
    simulated_staffed_beds: int
    projected_demand_beds: int
    shortfall_beds: int
    capacity_utilization_pct: float | None
    note: str = "Deterministic scenario calculation, not a validated epidemiological forecast."

class AlertReviewRequest(BaseModel):
    decision: Literal["acknowledged", "dismissed", "escalated"]
    note: str = Field(default="", max_length=2000)
    officer_id: str = Field(min_length=1, max_length=120)

class AlertReviewResponse(BaseModel):
    alert_id: str
    status: str
    reviewed_at: datetime
    audit_entry_hash: str

class SummaryReviewRequest(BaseModel):
    alert_id: str = Field(min_length=1, max_length=36)

class SummaryReviewResponse(BaseModel):
    alert_id: str
    provider: Literal["mock", "adaption"]
    mode: Literal["mock", "live"]
    review_status: str
    approved: bool
    reviewed_text: str | None
    issues: list[str]

class AudioBriefingRequest(BaseModel):
    alert_id: str = Field(min_length=1, max_length=36)

class AuditVerifyResponse(BaseModel):
    valid: bool
    checked_count: int
    first_invalid_event_id: str | None
    failure_reason: str | None

class IntegrationStatusOut(BaseModel):
    capability: str
    status: Literal["mock_active", "live_ready", "live_verified", "disabled", "missing_credential", "unsupported_contract", "configuration_error", "error"]
    mode: Literal["mock", "live"]
    enabled: bool
    credential_configured: bool
    endpoint_configured: bool
    contract_verified: bool
    message: str
