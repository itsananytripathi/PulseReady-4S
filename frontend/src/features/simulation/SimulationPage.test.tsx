import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SimulationPage } from './SimulationPage'

vi.mock('../../hooks/useApiQueries', () => ({
  useSimulation: () => ({ mutate: vi.fn(), isPending: false, isError: false, data: undefined }),
}))

describe('simulation form', () => {
  it('keeps the action disabled until the documented required facility is present', async () => {
    const client = new QueryClient()
    render(<QueryClientProvider client={client}><SimulationPage /></QueryClientProvider>)
    const button = screen.getByRole('button', { name: 'Run simulation' })
    expect(button).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Facility code'), 'A-01')
    expect(button).toBeEnabled()
  })
})
