import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { WorkItemsPage } from './WorkItemsPage'
import { planningApi } from '../workflow/api'
import { WorkflowProvider, clearWorkflowForTests, seedWorkflowForTests } from '../workflow/WorkflowContext'

vi.mock('../workflow/api', () => ({ planningApi: { sample: vi.fn(), review: vi.fn(), analyze: vi.fn(), generate: vi.fn() } }))
const workItem = { id: 'JOB-UNSEEN-908', title: {}, type: 'delivery', mandatory: true, customer_id: null, revenue_jpy: 0, direct_cost_jpy: 0, success_probability: 1, required_hours: 33.5, earliest_start: '2037-01-02', due_date: '2037-01-20', dependencies: ['PREREQ-ARBITRARY'], conflicts: [], required_languages: ['ja'], required_skills: [{ skill: 'react', min_level: 3 }, { skill: 'sql', min_level: 2 }], resource_requirements: [] }
const people = [
  { id: 'PERSON-BEST', name: 'Best Match', capacity_hours: 80, skills: { react: 4, sql: 3 }, languages: ['ja'] },
  { id: 'PERSON-PARTIAL', name: 'Partial Match', capacity_hours: 80, skills: { react: 4 }, languages: ['en'] },
  { id: 'PERSON-NO', name: 'No Match', capacity_hours: 10, skills: {}, languages: ['en'] },
]
const catalog = {
  summary: { dataset_id: 'UNSEEN', currency: 'JPY' },
  company: { name: 'Company', starting_cash_jpy: 1, minimum_cash_buffer_jpy: 0 },
  work_items: [workItem], people, customers: [], shared_resources: [], commercial_options: [], portfolio_effects: [],
} as any
const analysis = {
  feasibility: [{ work_item_id: 'JOB-UNSEEN-908', status: 'FEASIBLE', dependencies: { satisfied: true, required: ['PREREQ-ARBITRARY'], missing: [] }, capacity: { required_hours: 33.5, total_team_capacity_hours: 100, sufficient: true }, deadline: { status: 'WITHIN_HORIZON', due_date: '2037-01-20', days_until_due: 18 }, hard_failures: [], blockers: [], warnings: [] }],
  portfolio: {}, commercial: { opportunities: [] },
  scoring: { score_version: 'test', reasons: [], candidates: [{ action_id: 'JOB-UNSEEN-908', action_type: 'WORK_ITEM', work_item_id: 'JOB-UNSEEN-908', option_id: null, mandatory: true, selection_status: 'ELIGIBLE', eligible_for_selection: true, business_value_score: 0.9, reasons: [], warnings: [] }] },
} as any

function renderPage() {
  return render(<MemoryRouter><WorkflowProvider><WorkItemsPage /></WorkflowProvider></MemoryRouter>)
}
describe('WorkItems staged workflow', () => {
  beforeEach(() => { vi.clearAllMocks(); clearWorkflowForTests(); seedWorkflowForTests({ status: 'DATA_LOADED', source: 'sample', catalog }) })

  it('shows arbitrary work and missing optional names before analysis', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: 'JOB-UNSEEN-908' })).toBeInTheDocument()
    expect(screen.getByText('33.5 h')).toBeInTheDocument()
    expect(screen.getByText('PREREQ-ARBITRARY')).toBeInTheDocument()
    expect(screen.getByText('Not analyzed yet')).toBeInTheDocument()
    expect(screen.queryByText('Very high')).not.toBeInTheDocument()
    expect(planningApi.analyze).not.toHaveBeenCalled()
    expect(planningApi.generate).not.toHaveBeenCalled()
  })

  it('requires separate Analyze and Generate actions', async () => {
    vi.mocked(planningApi.analyze).mockResolvedValue(analysis)
    vi.mocked(planningApi.generate).mockResolvedValue({ ...analysis, plan: {}, cash_flow: {}, final_decision: {} } as any)
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: 'Analyze portfolio' }))
    expect(await screen.findByText('Portfolio analysis is ready')).toBeInTheDocument()
    expect(screen.getByText('Very high')).toBeInTheDocument()
    expect(screen.getByText('Can be performed')).toBeInTheDocument()
    expect(planningApi.analyze).toHaveBeenCalledTimes(1)
    expect(planningApi.generate).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Generate recommended plan' }))
    expect(await screen.findByRole('button', { name: 'Review execution plan' })).toBeInTheDocument()
    expect(planningApi.generate).toHaveBeenCalledTimes(1)
  })
  it('filters the work portfolio without assuming canonical categories or IDs', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: 'Other work' }))
    expect(screen.queryByRole('heading', { name: 'JOB-UNSEEN-908' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Mandatory' }))
    expect(screen.getByRole('heading', { name: 'JOB-UNSEEN-908' })).toBeInTheDocument()
  })
  it('suggests best, partial, and unsuitable employees when a generated-plan work item is selected', async () => {
    seedWorkflowForTests({
      status: 'PLAN_GENERATED', source: 'sample', catalog, analysis,
      generation: { ...analysis, plan: { person_capacity: [
        { person_id: 'PERSON-BEST', remaining_hours: 50 },
        { person_id: 'PERSON-PARTIAL', remaining_hours: 50 },
        { person_id: 'PERSON-NO', remaining_hours: 10 },
      ] }, cash_flow: {}, final_decision: {} } as any,
    })
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: 'JOB-UNSEEN-908' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Suggested employees/ })).toBeInTheDocument()
    expect(screen.getByText('Best Match')).toBeInTheDocument()
    expect(screen.getByText('Partial Match')).toBeInTheDocument()
    expect(screen.getByText('No Match')).toBeInTheDocument()
    expect(screen.getByText('Missing: sql')).toBeInTheDocument()
    expect(screen.queryByText('Audit details')).not.toBeInTheDocument()
  })
})
