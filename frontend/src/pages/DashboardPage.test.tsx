import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from './DashboardPage'
import { systemApi } from '../api/endpoints'

vi.mock('../api/endpoints', () => ({
  systemApi: { health: vi.fn(), baselineSummary: vi.fn() },
}))

const baseline = {
  dataset_id: 'DYNAMIC-DATASET', dataset_version: '9.4', planning_start: '2031-02-03', planning_end: '2031-02-28', currency: 'JPY',
  starting_cash_jpy: 12_345_678, minimum_cash_buffer_jpy: 4_321_000,
  people_count: 13, customer_count: 4, work_item_count: 37, commercial_option_count: 2,
  shared_resource_count: 3, portfolio_effect_count: 1, total_people_capacity_hours: 912.5,
  total_base_work_hours: 1200, mandatory_work_count: 8, mandatory_base_hours: 420,
  work_type_counts: { delivery: 37 },
}

describe('DashboardPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows a loading state while backend calls are pending', () => {
    vi.mocked(systemApi.health).mockReturnValue(new Promise(() => undefined))
    vi.mocked(systemApi.baselineSummary).mockReturnValue(new Promise(() => undefined))
    render(<DashboardPage />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading baseline data')
  })

  it('shows a structured error and retries', async () => {
    vi.mocked(systemApi.health).mockRejectedValueOnce(new Error('Backend unavailable')).mockResolvedValueOnce({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    render(<DashboardPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Backend unavailable')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(systemApi.health).toHaveBeenCalledTimes(2)
  })

  it('renders baseline values returned by the API without canonical constants', async () => {
    vi.mocked(systemApi.health).mockResolvedValue({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    render(<DashboardPage />)
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(screen.getByText('13')).toBeInTheDocument()
    expect(screen.getByText('37')).toBeInTheDocument()
    expect(screen.getByText(/12,345,678/)).toBeInTheDocument()
    expect(screen.getByText('DYNAMIC-DATASET')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
  })
})
