import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import { IntegrationsPage } from './IntegrationsPage'

vi.mock('../../hooks/useApiQueries', () => ({
  useIntegrationStatuses: () => ({ isLoading: false, isError: false, data: [
    { capability: 'adaption_labs', status: 'mock_active', mode: 'mock', enabled: true, credential_configured: true, endpoint_configured: true, contract_verified: true, message: 'Mock adapter is available.' },
    { capability: 'agent37_cloud', status: 'unsupported_contract', mode: 'mock', enabled: false, credential_configured: false, endpoint_configured: false, contract_verified: false, message: 'No verified contract.' },
  ], refetch: vi.fn() }),
  useOverview: () => ({ isLoading: false, isError: false, data: { active_alerts: [], readiness: [], generated_at: new Date().toISOString() }, refetch: vi.fn() }),
  useSummaryReview: () => ({ isPending: false, isError: false, isSuccess: false, mutate: vi.fn() }),
  useBriefingAudio: () => ({ isPending: false, isError: false, isSuccess: false, mutate: vi.fn() }),
}))

test('renders server integration states without claiming live operation', () => {
  const client = new QueryClient()
  render(<QueryClientProvider client={client}><IntegrationsPage /></QueryClientProvider>)
  expect(screen.getByRole('heading', { name: 'AI Ecosystem & Integrations' })).toBeInTheDocument()
  expect(screen.getByText('mock active')).toBeInTheDocument()
  expect(screen.getByText('unsupported contract')).toBeInTheDocument()
  expect(screen.getByText(/credentials stay server-side/i)).toBeInTheDocument()
})
