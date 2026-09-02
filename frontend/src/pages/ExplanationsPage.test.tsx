import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { WorkflowProvider, clearWorkflowForTests } from '../workflow/WorkflowContext'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { scenarioApi } from '../api/endpoints'
import type { ScenarioRun } from '../api/types'
import { ExplanationsPage } from './ExplanationsPage'

vi.mock('../api/endpoints', () => ({ scenarioApi: { getRun: vi.fn() } }))
const finding = (code: string, severity: string, sourcePhase: string, evidence: Record<string, unknown>, sourceId: string | null = null, actionId: string | null = null) => ({
  code, severity, source_phase: sourcePhase, source_id: sourceId, action_id: actionId, evidence,
})
const run = {
  run_id: 'RUN-EXPLAIN-ARBITRARY-71', scenario_id: 'SC-ANY', timestamp: '2035-03-01T00:00:00Z', status: 'COMPLETED', error: null,
  effective_input: { work_items: [
    { id: 'WORK-UNKNOWN-NO-BID-62', title: { en: 'Customer rollout' }, committed: true, mandatory: true, customer_id: 'CUSTOMER-7', dependencies: [], due_date: '2035-03-20' },
    { id: 'WORK-DELAY-81', title: { en: 'Internal migration' }, committed: false, mandatory: false, customer_id: null, dependencies: [] },
    { id: 'WORK-SELECT-55', title: { en: 'Growth package' }, committed: false, mandatory: false, customer_id: null, dependencies: [] },
  ] },
  final_decision: {
    executive_summary: {
      major_risks: ['CASH_TIMING_MISMATCH', 'BUFFER_BREACH'],
      major_strengths: ['PREREQUISITE_SELECTED'],
    },
    decision_explanations: [
      {
        work_item_id: 'WORK-UNKNOWN-NO-BID-62', action_id: 'ACTION-RARE-10', decision: 'NO_BID',
        reason_codes: ['NO_BID_CAPACITY_CONSTRAINT'],
        details: { required_hours: 99, available_hours: 40, completion_date: '2035-03-18', base_required_hours: 120 },
        findings: [finding('NO_BID_CAPACITY_CONSTRAINT', 'WARNING', 'COMMERCIAL', { candidate_ids: ['PERSON-ODD-8'] }, 'OPTION-ODD-3', 'ACTION-RARE-10')],
      },
      {
        work_item_id: 'WORK-DELAY-81', action_id: 'ACTION-DELAY-81', decision: 'DELAYED',
        reason_codes: ['DELAYED_CAPACITY_LIMIT'], details: { delay_days: 3 }, findings: [],
      },
      {
        work_item_id: 'WORK-SELECT-55', action_id: 'ACTION-SELECT-55', decision: 'SELECTED',
        reason_codes: ['SELECTED_BY_BUSINESS_VALUE'], details: { selected_option_id: 'OPTION-UNSEEN-902', score: 0.82 }, findings: [],
      },
    ],
    explanation_records: [
      finding('CASH_TIMING_MISMATCH', 'WARNING', 'CASH_FLOW', { receipt_date: '2035-05-20', horizon_end: '2035-04-30' }, 'OPTION-UNSEEN-902', null),
      finding('FUTURE_RECEIPT_OUTSIDE_HORIZON', 'INFO', 'CASH_FLOW', { expected_amount_jpy: 8_500_000 }, 'OPTION-UNSEEN-902', null),
      finding('BUFFER_BREACH', 'CRITICAL', 'FINAL_VALIDATION', { minimum_cash_jpy: 4_000_000, minimum_buffer_jpy: 5_000_000 }, null, null),
    ],
  },
} as unknown as ScenarioRun
function renderPage(entry = '/explanations?run_id=RUN-EXPLAIN-ARBITRARY-71') {
  return render(<MemoryRouter initialEntries={[entry]}><WorkflowProvider><ExplanationsPage /></WorkflowProvider></MemoryRouter>)
}
describe('ExplanationsPage', () => {
  beforeEach(() => { vi.clearAllMocks(); clearWorkflowForTests() })
  it('shows an empty state when no run is selected', () => {
    renderPage('/explanations')
    expect(screen.getByRole('heading', { name: 'Planning data is required first' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to Planning' })).toHaveAttribute('href', '/planning')
  })
  it('shows loading and run API error states', async () => {
    vi.mocked(scenarioApi.getRun).mockReturnValueOnce(new Promise(() => undefined))
    const view = renderPage()
    expect(screen.getByRole('status')).toBeInTheDocument()
    view.unmount()
    vi.mocked(scenarioApi.getRun).mockRejectedValueOnce(new Error('Unable to connect to the analysis system.'))
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to connect to the analysis system.')
  })
  it('renders friendly decisions without exposing structured reason codes', async () => {
    vi.mocked(scenarioApi.getRun).mockResolvedValue(run)
    renderPage()
    expect(await screen.findByText(/RUN-EXPLAIN-ARBITRARY-71/)).toBeInTheDocument()
    expect(screen.getByText('WORK-UNKNOWN-NO-BID-62')).toBeInTheDocument()
    expect(screen.queryByText('NO_BID_CAPACITY_CONSTRAINT')).not.toBeInTheDocument()
    expect(screen.getByText('The opportunity needs more team capacity than remains available.')).toBeInTheDocument()
    expect(screen.getByText('WORK-DELAY-81')).toBeInTheDocument()
    expect(screen.getByText('Delay')).toBeInTheDocument()
    expect(screen.getByText('WORK-SELECT-55')).toBeInTheDocument()
    expect(screen.getByText('Do')).toBeInTheDocument()
    expect(screen.getAllByText('OPTION-UNSEEN-902').length).toBeGreaterThan(0)
  })
  it('renders business evidence without the audit-only severity and source phase', async () => {
    vi.mocked(scenarioApi.getRun).mockResolvedValue(run)
    renderPage()
    expect(await screen.findByText('Delivery has already been committed to customer CUSTOMER-7.')).toBeInTheDocument()
    expect(screen.getByText('Expected handover')).toBeInTheDocument()
    expect(screen.queryByText('WARNING')).not.toBeInTheDocument()
    expect(screen.queryByText(/COMMERCIAL/)).not.toBeInTheDocument()
    expect(screen.queryByText(/CASH_FLOW/)).not.toBeInTheDocument()
    expect(screen.queryByText('ACTION-RARE-10')).not.toBeInTheDocument()
    expect(screen.queryByText('PERSON-ODD-8')).not.toBeInTheDocument()
    expect(screen.queryByText('Base required hours')).not.toBeInTheDocument()
    expect(screen.getByText('Effort needed')).toBeInTheDocument()
    expect(screen.getByText('99 h')).toBeInTheDocument()
  })
  it('renders cash timing, future receipt, and buffer breach findings from the run', async () => {
    vi.mocked(scenarioApi.getRun).mockResolvedValue(run)
    renderPage()
    expect(await screen.findByText('Large receipts arrive after the planning period, so they do not solve the current cash gap.')).toBeInTheDocument()
    expect(screen.getByText('This receipt arrives after the current planning period.')).toBeInTheDocument()
    expect(screen.getByText('Cash falls below the minimum safety level during the plan.')).toBeInTheDocument()
    expect(screen.getByText('Expected receipt date')).toBeInTheDocument()
    expect(screen.getByText(/8,500,000/)).toBeInTheDocument()
    expect(screen.queryByText('CRITICAL')).not.toBeInTheDocument()
    expect(screen.queryByText('Audit details')).not.toBeInTheDocument()
  })
})
