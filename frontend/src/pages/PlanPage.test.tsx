import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { WorkflowProvider, clearWorkflowForTests } from '../workflow/WorkflowContext'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { scenarioApi } from '../api/endpoints'
import type { ScenarioRun } from '../api/types'
import { PlanPage } from './PlanPage'

vi.mock('../api/endpoints', () => ({
  scenarioApi: { getRun: vi.fn() },
}))
const completeRun = {
  run_id: 'RUN-NONCANONICAL-88', scenario_id: 'SCENARIO-X', timestamp: '2034-03-04T10:00:00Z', status: 'COMPLETED', error: null,
  final_decision: {
    overall_status: 'PLAN_PARTIAL', operational_status: 'OPERATIONALLY_PARTIAL', financial_status: 'CASH_SAFE',
    capacity_summary: { total_capacity_hours: 80, total_used_hours: 6.5, total_remaining_hours: 73.5, people: [], violations: [] },
    mandatory_summary: { total_mandatory: 1, scheduled_count: 1, infeasible_count: 0, omitted_count: 0, outcomes: [
      { work_item_id: 'WORK-DELTA-91', scheduled: true, infeasible: false, omitted: false, prerequisite_ids: ['WORK-PREREQ-X'], completion_date: '2034-03-12' },
    ] },
  },
  plan: {
    status: 'PLAN_PARTIAL', selected_actions: ['ACTION-DELTA'], delayed_actions: ['ACTION-LATE'], no_bid_opportunities: ['WORK-SALES-X'],
    mandatory_infeasible: [],
    decisions: [
      { work_item_id: 'WORK-DELTA-91', action_id: 'ACTION-DELTA', decision: 'SELECTED', selected_option_id: null, prerequisite_ids: ['WORK-PREREQ-X'], unlock_trigger_ids: [], reason_codes: ['MANDATORY_SELECTED'] },
      { work_item_id: 'WORK-SALES-X', action_id: 'ACTION-SALES-X', decision: 'NO_BID', selected_option_id: null, prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: ['CAPACITY_EXHAUSTED'] },
    ],
    schedule: [{ date: '2034-03-10', action_id: 'ACTION-DELTA', person_id: 'PERSON-UNSEEN-5', hours: 6.5, allocation_type: 'WORK' }],
    assignments: [{ person_id: 'PERSON-UNSEEN-5', action_id: 'ACTION-DELTA', assigned_hours: 6.5, assignment_role: 'OWNER', skills_covered: ['quantum'], languages_covered: ['vi'] }],
    prerequisite_closures: [{ target_action_id: 'ACTION-DELTA', required_prerequisites: ['WORK-PREREQ-X'], unlock_triggers: [], completion_order: ['WORK-PREREQ-X', 'ACTION-DELTA'], cycle_detected: false, invalid_references: [] }],
    person_capacity: [{ person_id: 'PERSON-UNSEEN-5', capacity_hours: 80, used_hours: 6.5, remaining_hours: 73.5, available_days: 18, daily_capacity_hours: 4.4 }],
    resource_capacity: [{ resource_id: 'RESOURCE-NOVEL-3', capacity_hours: 40, used_hours: 12, remaining_hours: 28, exclusive: true }],
  },
  commercial: { opportunities: [
    { work_item_id: 'WORK-SALES-X', title: 'Novel opportunity', options: [
      { option_id: 'OPTION-RARE-2', work_item_id: 'WORK-SALES-X', label: 'Premium', availability: 'AVAILABLE', deliverability: 'INDIVIDUALLY_DELIVERABLE', selectable: true, win_probability: 0.63 },
    ] },
  ] },
} as unknown as ScenarioRun
function renderPlan(entry = '/plan?run_id=RUN-NONCANONICAL-88') {
  return render(<MemoryRouter initialEntries={[entry]}><WorkflowProvider><PlanPage /></WorkflowProvider></MemoryRouter>)
}
describe('PlanPage', () => {
  beforeEach(() => { vi.clearAllMocks(); clearWorkflowForTests() })
  it('shows a linked empty state when no run is selected', () => {
    renderPlan('/plan')
    expect(screen.getByRole('heading', { name: 'Planning data is required first' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to Planning' })).toHaveAttribute('href', '/planning')
    expect(scenarioApi.getRun).not.toHaveBeenCalled()
  })
  it('shows loading while the historical run is requested', () => {
    vi.mocked(scenarioApi.getRun).mockReturnValue(new Promise(() => undefined))
    renderPlan()
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(scenarioApi.getRun).toHaveBeenCalledWith('RUN-NONCANONICAL-88')
  })
  it('shows a retryable run loading error', async () => {
    vi.mocked(scenarioApi.getRun).mockRejectedValue(new Error('Unable to connect to the analysis system.'))
    renderPlan()
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to connect to the analysis system.')
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
  it('renders friendly decisions, mandatory outcomes, schedule, assignments, and prerequisites without audit details', async () => {
    vi.mocked(scenarioApi.getRun).mockResolvedValue(completeRun)
    renderPlan()
    expect(await screen.findByText(/RUN-NONCANONICAL-88/)).toBeInTheDocument()
    expect(screen.getAllByText('ACTION-LATE').length).toBeGreaterThan(0)
    expect(screen.queryByText('NO_BID')).not.toBeInTheDocument()
    expect(screen.getByText('This work is included because it is a mandatory commitment.')).toBeInTheDocument()
    expect(screen.getAllByText(/Mar 10, 2034/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/PERSON-UNSEEN-5/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Owner/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/WORK-PREREQ-X/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Depends on/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('This is mandatory work').length).toBeGreaterThan(0)
    expect(screen.queryByText('Audit details')).not.toBeInTheDocument()
  })
  it('renders person capacity, shared resources, and commercial decisions', async () => {
    vi.mocked(scenarioApi.getRun).mockResolvedValue(completeRun)
    renderPlan()
    expect(await screen.findByRole('heading', { name: 'Team allocation' })).toBeInTheDocument()
    expect(screen.getAllByText('Novel opportunity').length).toBeGreaterThan(0)
    expect(screen.queryByText(/OPTION-RARE-2/)).not.toBeInTheDocument()
    expect(screen.getByText(/63%/)).toBeInTheDocument()
    expect(screen.getAllByText(/6.5 h/).length).toBeGreaterThan(0)
  })
})
