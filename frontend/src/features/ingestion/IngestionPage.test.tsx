import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { IngestionPage } from './IngestionPage'
import { useIngestion } from '../../hooks/useApiQueries'

vi.mock('../../hooks/useApiQueries', () => ({ useIngestion: vi.fn() }))

describe('ingestion page', () => {
  it('shows server-confirmed ingestion results and row reasons', async () => {
    const mutate = vi.fn()
    vi.mocked(useIngestion).mockReturnValue({ mutate, isPending: false, isError: false, data: { accepted_rows: 1, rejected_rows: 1, rejected: [{ row_number: 3, reason: 'value must be finite' }], created_signal_ids: ['signal-a'], alerts_created: 0, note: 'Synthetic operational signal.' } } as never)
    render(<IngestionPage />)
    const input = screen.getByLabelText('CSV or JSON file')
    const file = new File(['facility_code,signal_type,observed_at,value'], 'synthetic.json', { type: 'application/json' })
    await userEvent.upload(input, file)
    await userEvent.click(screen.getByRole('button', { name: 'Submit to pipeline' }))
    expect(mutate).toHaveBeenCalledWith(file)
    expect(screen.getByText('value must be finite')).toBeInTheDocument()
  })

  it('does not show a success summary when the upload fails', () => {
    vi.mocked(useIngestion).mockReturnValue({ mutate: vi.fn(), isPending: false, isError: true, error: new Error('Failed to fetch'), data: undefined } as never)
    render(<IngestionPage />)
    expect(screen.getByRole('alert')).toHaveTextContent('backend is unreachable')
    expect(screen.queryByText('Server-confirmed result')).not.toBeInTheDocument()
  })
})
