import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getBriefingAudio, getHealth, getIntegrationStatuses, getOverview, ingest, reviewAlert, reviewSummary, simulate, verifyAudit } from '../lib/api/endpoints'
import type { AlertReviewRequest, SimulateRequest } from '../lib/api/contracts'

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: ({ signal }) => getHealth(signal), retry: false, refetchInterval: 30_000 })
}

export function useOverview() {
  return useQuery({ queryKey: ['overview'], queryFn: ({ signal }) => getOverview(signal), retry: false, staleTime: 15_000 })
}

export function useAuditVerification() {
  return useQuery({ queryKey: ['audit-verification'], queryFn: ({ signal }) => verifyAudit(signal), retry: false, staleTime: 0 })
}

export function useSimulation() {
  return useMutation({ mutationFn: (payload: SimulateRequest) => simulate(payload) })
}

export function useIngestion() {
  const client = useQueryClient()
  return useMutation({ mutationFn: (file: File) => ingest(file), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['overview'] }) } })
}

export function useAlertReview() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ alertId, payload }: { alertId: string; payload: AlertReviewRequest }) => reviewAlert(alertId, payload),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['overview'] }); await client.invalidateQueries({ queryKey: ['audit-verification'] }) },
  })
}

export function useIntegrationStatuses() {
  return useQuery({ queryKey: ['integration-statuses'], queryFn: ({ signal }) => getIntegrationStatuses(signal), retry: false, staleTime: 30_000 })
}

export function useSummaryReview() {
  const client = useQueryClient()
  return useMutation({ mutationFn: (alertId: string) => reviewSummary(alertId), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['audit-verification'] }) } })
}

export function useBriefingAudio() {
  const client = useQueryClient()
  return useMutation({ mutationFn: (alertId: string) => getBriefingAudio(alertId), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['audit-verification'] }) } })
}
