import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { DashboardPage } from './DashboardPage'
import { WorkflowProvider, clearWorkflowForTests, seedWorkflowForTests } from '../workflow/WorkflowContext'

const catalog = {
  summary: { dataset_id: 'UNSEEN-DS', currency: 'JPY' },
  company: { name: 'Dynamic Co', starting_cash_jpy: 50000000, minimum_cash_buffer_jpy: 5000000 },
  work_items: [], people: [], customers: [], shared_resources: [], commercial_options: [], portfolio_effects: [],
} as any
const plan = {
  status: 'PARTIAL',
  decisions: [
    { work_item_id: 'WORK-ONE', action_id: 'WORK-ONE-A', decision: 'SELECT_OPTION', selected_option_id: 'WORK-ONE-A', prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: [] },
    { work_item_id: 'WORK-ONE', action_id: 'WORK-ONE-B', decision: 'DELAY', selected_option_id: null, prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: [] },
    { work_item_id: 'WORK-TWO', action_id: 'WORK-TWO', decision: 'DELAY', selected_option_id: null, prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: [] },
    { work_item_id: 'WORK-THREE', action_id: 'WORK-THREE', decision: 'NO_BID', selected_option_id: null, prerequisite_ids: [], unlock_trigger_ids: [], reason_codes: [] },
  ],
  selected_actions: ['WORK-ONE-A'], delayed_actions: ['WORK-ONE-B', 'WORK-TWO'], no_bid_opportunities: ['WORK-THREE'],
  mandatory_infeasible: [], prerequisite_closures: [], assignments: [], schedule: [], person_capacity: [], resource_capacity: [],
} as any
const finalDecision = {
  overall_status: 'PLAN_PARTIAL', operational_status: 'OPERATIONALLY_PARTIAL', financial_status: 'CASH_SAFE',
  executive_summary: { selected_count: 12, delayed_count: 3, no_bid_count: 1, mandatory_total: 4, mandatory_scheduled_count: 4, total_capacity_hours: 800, total_used_hours: 540, total_remaining_hours: 260, first_buffer_breach_date: null },
  mandatory_summary: { total_mandatory: 4, scheduled_count: 4, infeasible_count: 0, omitted_count: 0, outcomes: [] },
  capacity_summary: { total_capacity_hours: 800, total_used_hours: 540, total_remaining_hours: 260, people: [{ person_id: 'PERSON-UNSEEN', capacity_hours: 160, used_hours: 152, remaining_hours: 8, utilisation_pct: 95 }], violations: [] },
  cash_summary: { starting_cash_jpy: 50000000, minimum_buffer_jpy: 5000000, financial_status: 'CASH_SAFE', scenarios: [{ scenario: 'EXPECTED', status: 'CASH_SAFE', ending_cash_jpy: 32000000, minimum_cash_jpy: 16000000, minimum_cash_date: '2031-04-15', first_buffer_breach_date: null, days_below_buffer: 0, negative_cash: false }], future_receipts: [], findings: [] },
  decision_explanations: [], validations: [], warnings: [], critical_issues: [], explanation_records: [], source_versions: {}, assumptions_used: {},
} as any

describe('Generated plan executive summary', () => {
  beforeEach(() => {
    clearWorkflowForTests()
    seedWorkflowForTests({ status: 'PLAN_GENERATED', source: 'sample', catalog, generation: { final_decision: finalDecision, plan } as any })
  })

  it('shows dynamic plan decisions, capacity and cash only after generation', () => {
    render(<MemoryRouter><WorkflowProvider><DashboardPage /></WorkflowProvider></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Business health at a glance' })).toBeInTheDocument()
    expect(screen.getByTestId('count-Selected')).toHaveTextContent('1')
    expect(screen.getByTestId('count-Delayed')).toHaveTextContent('1')
    expect(screen.getByTestId('count-No-bid')).toHaveTextContent('1')
    expect(screen.getByText('PERSON-UNSEEN')).toBeInTheDocument()
    expect(screen.getByTestId('cash-scenario-EXPECTED')).toHaveTextContent(/32,000,000|32.000.000/)
  })
})
