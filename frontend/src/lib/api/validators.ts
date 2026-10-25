import type { AlertReviewResponse, AuditVerifyResponse, HealthResponse, IngestSummary, IntegrationStatusOut, OverviewOut, SimulateResponse, SummaryReviewResponse } from './contracts'

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`Malformed ${label} response.`)
  return value as Record<string, unknown>
}

function string(value: unknown, label: string): string {
  if (typeof value !== 'string') throw new Error(`Malformed ${label} response.`)
  return value
}

function number(value: unknown, label: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`Malformed ${label} response.`)
  return value
}

export function parseHealth(value: unknown): HealthResponse {
  const item = record(value, 'health')
  return { status: string(item.status, 'health'), mode: string(item.mode, 'health') }
}

export function parseOverview(value: unknown): OverviewOut {
  const item = record(value, 'overview')
  if (!Array.isArray(item.readiness) || !Array.isArray(item.active_alerts)) throw new Error('Malformed overview response.')
  return value as OverviewOut
}

export function parseAudit(value: unknown): AuditVerifyResponse {
  const item = record(value, 'audit verification')
  if (typeof item.valid !== 'boolean' || !Number.isInteger(item.checked_count) || (item.first_invalid_event_id !== null && typeof item.first_invalid_event_id !== 'string') || (item.failure_reason !== null && typeof item.failure_reason !== 'string')) throw new Error('Malformed audit verification response.')
  return value as AuditVerifyResponse
}

export function parseIngest(value: unknown): IngestSummary {
  const item = record(value, 'ingestion')
  if (!Number.isInteger(item.accepted_rows) || !Number.isInteger(item.rejected_rows) || !Array.isArray(item.rejected) || !Array.isArray(item.created_signal_ids) || !Number.isInteger(item.alerts_created) || typeof item.note !== 'string') throw new Error('Malformed ingestion response.')
  return value as IngestSummary
}

export function parseSimulation(value: unknown): SimulateResponse {
  const item = record(value, 'simulation')
  if (typeof item.simulation_id !== 'string' || typeof item.facility_code !== 'string' || !Number.isInteger(item.baseline_staffed_beds) || !Number.isInteger(item.simulated_staffed_beds) || !Number.isInteger(item.projected_demand_beds) || !Number.isInteger(item.shortfall_beds) || (item.capacity_utilization_pct !== null && typeof item.capacity_utilization_pct !== 'number') || typeof item.note !== 'string') throw new Error('Malformed simulation response.')
  return value as SimulateResponse
}

export function parseReview(value: unknown): AlertReviewResponse {
  const item = record(value, 'alert review')
  if (typeof item.alert_id !== 'string' || typeof item.status !== 'string' || typeof item.reviewed_at !== 'string' || typeof item.audit_entry_hash !== 'string') throw new Error('Malformed alert review response.')
  return value as AlertReviewResponse
}

export function parseIntegrationStatuses(value: unknown): IntegrationStatusOut[] {
  if (!Array.isArray(value)) throw new Error('Malformed integration status response.')
  return value.map((entry) => {
    const item = record(entry, 'integration status')
    if (typeof item.capability !== 'string' || !['mock_active', 'live_ready', 'live_verified', 'disabled', 'missing_credential', 'unsupported_contract', 'configuration_error', 'error'].includes(String(item.status)) || !['mock', 'live'].includes(String(item.mode)) || typeof item.enabled !== 'boolean' || typeof item.credential_configured !== 'boolean' || typeof item.endpoint_configured !== 'boolean' || typeof item.contract_verified !== 'boolean' || typeof item.message !== 'string') throw new Error('Malformed integration status response.')
    return item as unknown as IntegrationStatusOut
  })
}

export function parseSummaryReview(value: unknown): SummaryReviewResponse {
  const item = record(value, 'summary review')
  if (typeof item.alert_id !== 'string' || !['mock', 'adaption'].includes(String(item.provider)) || !['mock', 'live'].includes(String(item.mode)) || typeof item.review_status !== 'string' || typeof item.approved !== 'boolean' || (item.reviewed_text !== null && typeof item.reviewed_text !== 'string') || !Array.isArray(item.issues) || !item.issues.every((issue) => typeof issue === 'string')) throw new Error('Malformed summary review response.')
  return item as unknown as SummaryReviewResponse
}

// Keep these helpers exercised by endpoint tests without duplicating schemas in the UI.
export { number, string }
