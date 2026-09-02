import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from './DashboardPage'
import { planningApi } from '../workflow/api'
import { WorkflowProvider, clearWorkflowForTests } from '../workflow/WorkflowContext'

vi.mock('../workflow/api', () => ({ planningApi: { sample: vi.fn(), review: vi.fn(), analyze: vi.fn(), generate: vi.fn() } }))

const catalog = {
  summary: { dataset_id: 'DYNAMIC-SAMPLE', planning_start: '2032-01-01', planning_end: '2032-01-28', currency: 'JPY', work_item_count: 31, people_count: 9, total_people_capacity_hours: 777, commercial_option_count: 4, shared_resource_count: 2, portfolio_effect_count: 3, starting_cash_jpy: 12345678, minimum_cash_buffer_jpy: 2500000 },
  company: { name: 'Nexa Dynamic', starting_cash_jpy: 12345678, minimum_cash_buffer_jpy: 2500000 },
  work_items: [], people: [], customers: [], shared_resources: [], commercial_options: [], portfolio_effects: [],
} as any

function renderPage() {
  return render(<MemoryRouter><WorkflowProvider><DashboardPage /></WorkflowProvider></MemoryRouter>)
}

describe('Dashboard workflow entry', () => {
  beforeEach(() => { vi.clearAllMocks(); clearWorkflowForTests() })

  it('shows a planning entry instead of unexplained final results', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: 'Build your operating plan' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create new plan' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Use sample data' })).toBeInTheDocument()
    expect(planningApi.generate).not.toHaveBeenCalled()
  })

  it('loads the sample into review without analyzing or generating it', async () => {
    vi.mocked(planningApi.sample).mockResolvedValue(catalog)
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: 'Use sample data' }))
    expect(await screen.findByRole('heading', { name: 'Analyze the work portfolio first' })).toBeInTheDocument()
    expect(planningApi.sample).toHaveBeenCalledTimes(1)
    expect(planningApi.analyze).not.toHaveBeenCalled()
    expect(planningApi.generate).not.toHaveBeenCalled()
  })
})
