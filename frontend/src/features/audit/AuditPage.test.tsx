import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AuditPage } from './AuditPage'
import { useAlertReview, useAuditVerification, useOverview } from '../../hooks/useApiQueries'

vi.mock('../../hooks/useApiQueries', () => ({ useAuditVerification: vi.fn(), useOverview: vi.fn(), useAlertReview: vi.fn() }))

describe('audit page', () => {
  it('distinguishes completed invalid verification from request failure', () => {
    vi.mocked(useAuditVerification).mockReturnValue({ data: { valid: false, checked_count: 3, first_invalid_event_id: 'event-a', failure_reason: 'event_hash_mismatch' }, isLoading: false, isError: false } as never)
    vi.mocked(useOverview).mockReturnValue({ data: { readiness: [], active_alerts: [] }, isLoading: false, isError: false } as never)
    vi.mocked(useAlertReview).mockReturnValue({ mutate: vi.fn(), isPending: false, isSuccess: false, isError: false } as never)
    render(<AuditPage />)
    expect(screen.getByText('Integrity problem detected')).toBeInTheDocument()
    expect(screen.getByText(/event_hash_mismatch/)).toBeInTheDocument()
  })
})
