import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { OverviewPage } from './OverviewPage'
import { useOverview } from '../../hooks/useApiQueries'

vi.mock('../../hooks/useApiQueries', () => ({ useOverview: vi.fn() }))

const overview = { generated_at: '2026-10-23T10:00:00Z', readiness: [{ facility_id: 'facility-a', facility_code: 'A-01', facility_name: 'Synthetic Hospital', staff_score: 90, stuff_score: 80, space_score: 70, system_score: 95, overall_score: 83.75, supply_buffer_days: 6, supply_status: 'adequate' as const, staffed_beds: 80, total_beds: 100 }], active_alerts: [] }

describe('overview page', () => {
  it('renders the actual contract-shaped readiness fields', () => {
    vi.mocked(useOverview).mockReturnValue({ data: overview, isLoading: false, isError: false } as never)
    render(<OverviewPage />)
    expect(screen.getByText('Synthetic Hospital')).toBeInTheDocument()
    expect(screen.getByText('83.8')).toBeInTheDocument()
    expect(screen.getByText('6 days')).toBeInTheDocument()
  })

  it('shows a disconnected state without fake readiness cards', () => {
    vi.mocked(useOverview).mockReturnValue({ data: undefined, isLoading: false, isError: true, error: new Error('Failed to fetch') } as never)
    render(<OverviewPage />)
    expect(screen.getByRole('alert')).toHaveTextContent('backend is unreachable')
    expect(screen.queryByText('Overall readiness')).not.toBeInTheDocument()
  })
})
