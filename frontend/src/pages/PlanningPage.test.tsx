import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PlanningPage } from './PlanningPage'
import { planningApi } from '../workflow/api'
import { WorkflowProvider, clearWorkflowForTests } from '../workflow/WorkflowContext'

vi.mock('../workflow/api', () => ({ planningApi: { sample: vi.fn(), review: vi.fn(), analyze: vi.fn(), generate: vi.fn() } }))
const catalog = {
  summary: { dataset_id: 'UNSEEN-DATASET', planning_start: '2036-02-01', planning_end: '2036-02-28', currency: 'JPY', work_item_count: 47, people_count: 11, total_people_capacity_hours: 987.5, commercial_option_count: 6, shared_resource_count: 5, portfolio_effect_count: 2, starting_cash_jpy: 76543210, minimum_cash_buffer_jpy: 4567000 },
  company: { name: 'Unseen Co', starting_cash_jpy: 76543210, minimum_cash_buffer_jpy: 4567000 },
  work_items: [], people: [], customers: [], shared_resources: [], commercial_options: [], portfolio_effects: [],
} as any

describe('PlanningPage', () => {
  beforeEach(() => { vi.clearAllMocks(); clearWorkflowForTests() })
  it('loads sample data into review without running analysis or planning', async () => {
    vi.mocked(planningApi.sample).mockResolvedValue(catalog)
    render(<MemoryRouter><WorkflowProvider><PlanningPage /></WorkflowProvider></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: 'Use sample data' }))
    expect(await screen.findByRole('heading', { name: 'Planning data is ready for review' })).toBeInTheDocument()
    expect(screen.getByText('47')).toBeInTheDocument()
    expect(screen.getByText('987.5 h')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Review work items' })).toBeInTheDocument()
    expect(planningApi.analyze).not.toHaveBeenCalled()
    expect(planningApi.generate).not.toHaveBeenCalled()
  })
  it('shows a useful error when sample data cannot be loaded', async () => {
    vi.mocked(planningApi.sample).mockRejectedValue(new Error('offline'))
    render(<MemoryRouter><WorkflowProvider><PlanningPage /></WorkflowProvider></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: 'Use sample data' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded')
    expect(planningApi.analyze).not.toHaveBeenCalled()
  })
})
