import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { WorkflowProvider, clearWorkflowForTests } from '../workflow/WorkflowContext'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { scenarioApi } from '../api/endpoints'
import type { ScenarioRun } from '../api/types'
import { CashFlowPage } from './CashFlowPage'

vi.mock('../api/endpoints', () => ({ scenarioApi: { getRun: vi.fn() } }))
const day = (date: string, closing: number, breach = false, negative = false) => ({
  date, opening_cash_jpy: 12_000_000, cash_in_jpy: 500_000, cash_out_jpy: 1_000_000, net_change_jpy: -500_000,
  closing_cash_jpy: closing, minimum_buffer_jpy: 5_000_000, buffer_headroom_jpy: closing - 5_000_000,
  buffer_breach: breach, negative_cash: negative, events: [],
})
const cashScenario = (scenario: string, status: string, ending: number) => ({
  scenario, status, timeline: [day('2035-04-01', 11_500_000), day('2035-04-02', ending, status !== 'CASH_SAFE', status === 'NEGATIVE_CASH')],
  in_horizon_events: [], future_events: [], total_cash_in_jpy: 500_000, total_cash_out_jpy: 2_000_000, event_totals_jpy: {},
  minimum_cash_jpy: ending, minimum_cash_date: '2035-04-02', ending_cash_jpy: ending,
  first_buffer_breach_date: status === 'CASH_SAFE' ? null : '2035-04-02', days_below_buffer: status === 'CASH_SAFE' ? 0 : 1,
  buffer_breach_dates: status === 'CASH_SAFE' ? [] : ['2035-04-02'], negative_cash_dates: status === 'NEGATIVE_CASH' ? ['2035-04-02'] : [],
})
const run = {
  run_id: 'RUN-CASH-ARBITRARY', scenario_id: 'SC-X', timestamp: '2035-04-01T00:00:00Z', status: 'COMPLETED', error: null,
  cash_flow: {
    overall_status: 'BUFFER_BREACH', operational_plan_status: 'PARTIAL', starting_cash_jpy: 12_000_000, minimum_buffer_jpy: 5_000_000,
    scenarios: {
      EXPECTED: cashScenario('EXPECTED', 'CASH_SAFE', 9_000_000),
      DOWNSIDE: cashScenario('DOWNSIDE', 'BUFFER_BREACH', 4_000_000),
      SUCCESS: cashScenario('SUCCESS', 'CASH_SAFE', 14_000_000),
    },
    future_events: [{
      event_id: 'EVENT-FUTURE-X', date: '2035-05-20', source_type: 'COMMERCIAL_OPTION', source_id: 'OPTION-FUTURE-77',
      event_type: 'COMMERCIAL_RECEIPT', scenario: 'SUCCESS', amount_jpy: 8_500_000, direction: 'IN', deterministic: false,
      probability: 0.7, timing_basis: 'payment_days', outside_horizon: true, evidence: {},
    }],
    reasons: [], warnings: [], assumptions_used: {},
  },
} as unknown as ScenarioRun
function renderPage(entry = '/cash-flow?run_id=RUN-CASH-ARBITRARY') {
  return render(<MemoryRouter initialEntries={[entry]}><WorkflowProvider><CashFlowPage /></WorkflowProvider></MemoryRouter>)
}
describe('CashFlowPage', () => {
  beforeEach(() => { vi.clearAllMocks(); clearWorkflowForTests() })
  it('shows an empty state when no run is selected', () => {
    renderPage('/cash-flow')
    expect(screen.getByRole('heading', { name: 'Planning data is required first' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to Planning' })).toHaveAttribute('href', '/planning')
  })
  it('shows loading and API error states', async () => {
    vi.mocked(scenarioApi.getRun).mockReturnValueOnce(new Promise(() => undefined))
    const view = renderPage()
    expect(screen.getByRole('status')).toBeInTheDocument()
    view.unmount()
    vi.mocked(scenarioApi.getRun).mockRejectedValueOnce(new Error('Unable to connect to the analysis system.'))
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to connect to the analysis system.')
  })
  it('renders scenario statuses, ending and minimum cash, and breach details', async () => {
    vi.mocked(scenarioApi.getRun).mockResolvedValue(run)
    renderPage()
    expect(await screen.findByText(/RUN-CASH-ARBITRARY/)).toBeInTheDocument()
    expect(screen.getAllByText('Expected').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Downside case').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Cash falls below the safety level').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/4,000,000/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Apr 2, 2035/).length).toBeGreaterThan(0)
  })
  it('renders future receipts and clearly marks receipts outside the horizon', async () => {
    vi.mocked(scenarioApi.getRun).mockResolvedValue(run)
    renderPage()
    expect(await screen.findByText('OPTION-FUTURE-77')).toBeInTheDocument()
    expect(screen.getByText(/8,500,000/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Cash will arrive after the planning period' })).toBeInTheDocument()
    expect(screen.getAllByText('Favourable case').length).toBeGreaterThan(0)
  })
  it('renders the run-provided daily timeline and cash chart', async () => {
    vi.mocked(scenarioApi.getRun).mockResolvedValue(run)
    renderPage()
    expect(await screen.findByTestId('cash-chart')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Closing cash over time by scenario' })).toBeInTheDocument()
    expect(screen.getByText('Daily evidence')).toBeInTheDocument()
    expect(screen.getAllByText(/Apr 1, 2035/).length).toBeGreaterThan(0)
  })
})
