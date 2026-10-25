export type SupplyStatus = 'unknown' | 'critical' | 'low' | 'adequate'

export interface HealthResponse {
  status: string
  mode: string
}

export interface ReadinessOut {
  facility_id: string
  facility_code: string
  facility_name: string
  staff_score: number
  stuff_score: number
  space_score: number
  system_score: number
  overall_score: number
  supply_buffer_days: number | null
  supply_status: SupplyStatus
  staffed_beds: number
  total_beds: number
}

export interface AlertOut {
  id: string
  facility_id: string
  facility_code: string
  severity: string
  status: string
  title: string
  explanation: string
  created_at: string
}

export interface OverviewOut {
  generated_at: string
  readiness: ReadinessOut[]
  active_alerts: AlertOut[]
}

export interface IngestSummary {
  accepted_rows: number
  rejected_rows: number
  rejected: Array<Record<string, unknown>>
  created_signal_ids: string[]
  alerts_created: number
  note: string
}

export interface SimulateRequest {
  facility_code: string
  baseline_demand_beds: number
  demand_uplift_pct: number
  absenteeism_pct: number
}

export interface SimulateResponse {
  simulation_id: string
  facility_code: string
  baseline_staffed_beds: number
  simulated_staffed_beds: number
  projected_demand_beds: number
  shortfall_beds: number
  capacity_utilization_pct: number | null
  note: string
}

export type ReviewDecision = 'acknowledged' | 'dismissed' | 'escalated'

export interface AlertReviewRequest {
  decision: ReviewDecision
  note: string
  officer_id: string
}

export interface AlertReviewResponse {
  alert_id: string
  status: string
  reviewed_at: string
  audit_entry_hash: string
}

export interface AuditVerifyResponse {
  valid: boolean
  checked_count: number
  first_invalid_event_id: string | null
  failure_reason: string | null
}

export type IntegrationStatus = 'mock_active' | 'live_ready' | 'live_verified' | 'disabled' | 'missing_credential' | 'unsupported_contract' | 'configuration_error' | 'error'

export interface IntegrationStatusOut {
  capability: string
  status: IntegrationStatus
  mode: 'mock' | 'live'
  enabled: boolean
  credential_configured: boolean
  endpoint_configured: boolean
  contract_verified: boolean
  message: string
}

export interface SummaryReviewResponse {
  alert_id: string
  provider: 'mock' | 'adaption'
  mode: 'mock' | 'live'
  review_status: string
  approved: boolean
  reviewed_text: string | null
  issues: string[]
}
