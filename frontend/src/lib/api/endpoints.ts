import { getApiConfig, request, requestBlob } from './client'
import type { AlertReviewRequest, AlertReviewResponse, AuditVerifyResponse, HealthResponse, IngestSummary, IntegrationStatusOut, OverviewOut, SimulateRequest, SimulateResponse, SummaryReviewResponse } from './contracts'
import { parseAudit, parseHealth, parseIngest, parseIntegrationStatuses, parseOverview, parseReview, parseSimulation, parseSummaryReview } from './validators'

export function getHealth(signal?: AbortSignal) {
  return request<unknown>('/healthz', { signal }, false).then(parseHealth) as Promise<HealthResponse>
}

export function getOverview(signal?: AbortSignal) {
  return request<unknown>('/api/v1/overview', { signal }).then(parseOverview) as Promise<OverviewOut>
}

export function verifyAudit(signal?: AbortSignal) {
  return request<unknown>('/api/v1/audit/verify', { signal }).then(parseAudit) as Promise<AuditVerifyResponse>
}

export function simulate(payload: SimulateRequest, signal?: AbortSignal) {
  return request<unknown>('/api/v1/simulate', { method: 'POST', body: JSON.stringify(payload), signal }).then(parseSimulation) as Promise<SimulateResponse>
}

export function reviewAlert(alertId: string, payload: AlertReviewRequest, signal?: AbortSignal) {
  return request<unknown>(`/api/v1/alerts/${encodeURIComponent(alertId)}/review`, { method: 'POST', body: JSON.stringify(payload), signal }).then(parseReview) as Promise<AlertReviewResponse>
}

export function ingest(file: File, signal?: AbortSignal) {
  const form = new FormData()
  form.append('file', file)
  return request<unknown>('/api/v1/ingest', { method: 'POST', body: form, signal }).then(parseIngest) as Promise<IngestSummary>
}

export function getIntegrationStatuses(signal?: AbortSignal) {
  return request<unknown>('/api/v1/integrations/status', { signal }).then(parseIntegrationStatuses) as Promise<IntegrationStatusOut[]>
}

export function reviewSummary(alertId: string, signal?: AbortSignal) {
  return request<unknown>('/api/v1/review/summary', { method: 'POST', body: JSON.stringify({ alert_id: alertId }), signal }).then(parseSummaryReview) as Promise<SummaryReviewResponse>
}

export function getBriefingAudio(alertId: string, signal?: AbortSignal) {
  return requestBlob('/api/v1/briefings/audio', { method: 'POST', body: JSON.stringify({ alert_id: alertId }), signal })
}

export function apiBaseUrl() {
  return getApiConfig().baseUrl
}
