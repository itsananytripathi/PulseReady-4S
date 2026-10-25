import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AlertsPage } from './AlertsPage'
import { useAlertReview, useOverview } from '../../hooks/useApiQueries'

vi.mock('../../hooks/useApiQueries', () => ({ useOverview: vi.fn(), useAlertReview: vi.fn() }))

const alert = { id: 'alert-a', facility_id: 'facility-a', facility_code: 'A-01', severity: 'review', status: 'open', title: 'Unusual synthetic signal', explanation: 'Synthetic evidence for human review.', created_at: '2026-10-23T10:00:00Z' }

describe('alert review page', () => {
  it('submits the exact review payload only after officer input', async () => {
    const mutate = vi.fn()
    vi.mocked(useOverview).mockReturnValue({ data: { generated_at: alert.created_at, readiness: [], active_alerts: [alert] }, isLoading: false, isError: false } as never)
    vi.mocked(useAlertReview).mockReturnValue({ mutate, isPending: false, isSuccess: false, isError: false } as never)
    render(<AlertsPage />)
    expect(screen.getByRole('button', { name: 'Submit review' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Officer ID for Unusual synthetic signal'), 'officer-a')
    await userEvent.click(screen.getByRole('button', { name: 'Submit review' }))
    expect(mutate).toHaveBeenCalledWith({ alertId: 'alert-a', payload: { decision: 'acknowledged', note: '', officer_id: 'officer-a' } })
  })

  it('preserves the alert context and shows review failures', () => {
    vi.mocked(useOverview).mockReturnValue({ data: { generated_at: alert.created_at, readiness: [], active_alerts: [alert] }, isLoading: false, isError: false } as never)
    vi.mocked(useAlertReview).mockReturnValue({ mutate: vi.fn(), isPending: false, isSuccess: false, isError: true, error: new Error('server') } as never)
    render(<AlertsPage />)
    expect(screen.getByText('Unusual synthetic signal')).toBeInTheDocument()
    expect(screen.getAllByRole('alert').length).toBeGreaterThan(0)
  })
})
