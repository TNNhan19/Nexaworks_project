import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from './DashboardPage'
import { systemApi, decisionApi } from '../api/endpoints'
import type { FinalDecisionResult, BaselineSummary } from '../api/types'

vi.mock('../api/endpoints', () => ({
  systemApi: { health: vi.fn(), baselineSummary: vi.fn() },
  decisionApi: { finalDecision: vi.fn() },
}))

// ─── Fixtures ──────────────────────────────────────────────────────────────

const baseline: BaselineSummary = {
  dataset_id: 'TEST-DS', dataset_version: '1.0',
  planning_start: '2031-01-01', planning_end: '2031-06-30',
  currency: 'JPY',
  starting_cash_jpy: 50_000_000, minimum_cash_buffer_jpy: 5_000_000,
  people_count: 10, customer_count: 3, work_item_count: 20,
  commercial_option_count: 2, shared_resource_count: 1,
  portfolio_effect_count: 0, total_people_capacity_hours: 800,
  total_base_work_hours: 600, mandatory_work_count: 4, mandatory_base_hours: 200,
  work_type_counts: { delivery: 20 },
}

const decision: FinalDecisionResult = {
  overall_status: 'PLAN_PARTIAL',
  operational_status: 'OPERATIONALLY_PARTIAL',
  financial_status: 'CASH_SAFE',
  executive_summary: {
    plan_status: 'PLAN_PARTIAL',
    operational_status: 'OPERATIONALLY_PARTIAL',
    financial_status: 'CASH_SAFE',
    selected_count: 12,
    delayed_count: 3,
    no_bid_count: 1,
    mandatory_total: 4,
    mandatory_scheduled_count: 4,
    mandatory_infeasible_count: 0,
    total_capacity_hours: 800,
    total_used_hours: 540,
    total_remaining_hours: 260,
    expected_ending_cash_jpy: 32_000_000,
    downside_ending_cash_jpy: 18_500_000,
    success_ending_cash_jpy: 47_000_000,
    minimum_cash_jpy: 16_000_000,
    minimum_cash_date: '2031-04-15',
    first_buffer_breach_date: null,
    major_risks: ['CASH_BUFFER_BREACH'],
    major_strengths: ['PLAN_FINANCIALLY_SAFE'],
  },
  mandatory_summary: {
    total_mandatory: 4, scheduled_count: 4, infeasible_count: 0, omitted_count: 0, outcomes: [],
  },
  capacity_summary: {
    total_capacity_hours: 800,
    total_used_hours: 540,
    total_remaining_hours: 260,
    people: [
      { person_id: 'P001', capacity_hours: 160, used_hours: 152, remaining_hours: 8, utilisation_pct: 95 },
      { person_id: 'P002', capacity_hours: 160, used_hours: 80, remaining_hours: 80, utilisation_pct: 50 },
    ],
    violations: [],
  },
  cash_summary: {
    starting_cash_jpy: 50_000_000,
    minimum_buffer_jpy: 5_000_000,
    financial_status: 'CASH_SAFE',
    scenarios: [
      { scenario: 'EXPECTED', status: 'CASH_SAFE', ending_cash_jpy: 32_000_000, minimum_cash_jpy: 16_000_000, minimum_cash_date: '2031-04-15', first_buffer_breach_date: null, days_below_buffer: 0, negative_cash: false },
      { scenario: 'DOWNSIDE', status: 'CASH_SAFE', ending_cash_jpy: 18_500_000, minimum_cash_jpy: 10_000_000, minimum_cash_date: '2031-05-01', first_buffer_breach_date: null, days_below_buffer: 0, negative_cash: false },
      { scenario: 'SUCCESS',  status: 'CASH_SAFE', ending_cash_jpy: 47_000_000, minimum_cash_jpy: 22_000_000, minimum_cash_date: '2031-03-10', first_buffer_breach_date: null, days_below_buffer: 0, negative_cash: false },
    ],
    future_receipts: [
      { source_id: 'OPT-001', event_type: 'COMMERCIAL_CASH_RECEIPT', date: '2031-08-01', expected_amount_jpy: 8_000_000 },
    ],
    findings: [],
  },
  decision_explanations: [],
  validations: [],
  warnings: [],
  critical_issues: [],
  explanation_records: [
    { code: 'CASH_BUFFER_BREACH', severity: 'WARNING', source_phase: 'CASH_FLOW', source_id: null, action_id: null, evidence: {} },
    { code: 'PLAN_FINANCIALLY_SAFE', severity: 'INFO', source_phase: 'FINAL_VALIDATION', source_id: null, action_id: null, evidence: {} },
  ],
  source_versions: { planner: '2E', cash: '2F', final_validation: '2G' },
  assumptions_used: {},
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function setupMocks(opts: { failWith?: Error } = {}) {
  if (opts.failWith) {
    vi.mocked(systemApi.health).mockRejectedValue(opts.failWith)
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    vi.mocked(decisionApi.finalDecision).mockResolvedValue(decision)
  } else {
    vi.mocked(systemApi.health).mockResolvedValue({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    vi.mocked(decisionApi.finalDecision).mockResolvedValue(decision)
  }
}

// ─── Tests ─────────────────────────────────────────────────────────────────

describe('DashboardPage (Phase 5B)', () => {
  beforeEach(() => vi.clearAllMocks())

  // Loading state
  it('shows a loading state while API calls are pending', () => {
    vi.mocked(systemApi.health).mockReturnValue(new Promise(() => undefined))
    vi.mocked(systemApi.baselineSummary).mockReturnValue(new Promise(() => undefined))
    vi.mocked(decisionApi.finalDecision).mockReturnValue(new Promise(() => undefined))
    render(<DashboardPage />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading baseline data')
  })

  // Error + retry
  it('shows error alert and retries all calls on click', async () => {
    vi.mocked(systemApi.health).mockRejectedValueOnce(new Error('Connection refused')).mockResolvedValueOnce({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    vi.mocked(decisionApi.finalDecision).mockResolvedValue(decision)
    render(<DashboardPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Connection refused')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(systemApi.health).toHaveBeenCalledTimes(2)
    expect(decisionApi.finalDecision).toHaveBeenCalledTimes(2)
  })

  // Status badges
  it('renders all three status badges with correct text', async () => {
    setupMocks()
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    // overall = PLAN_PARTIAL → "Partial"
    expect(screen.getByTestId('badge-overall')).toHaveTextContent('Partial')
    // operational = OPERATIONALLY_PARTIAL → "Partial"
    expect(screen.getByTestId('badge-operational')).toHaveTextContent('Partial')
    // financial = CASH_SAFE → "Cash Safe"
    expect(screen.getByTestId('badge-financial')).toHaveTextContent('Cash Safe')
  })

  it('applies correct CSS class for PLAN_AT_RISK status', async () => {
    vi.mocked(systemApi.health).mockResolvedValue({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    vi.mocked(decisionApi.finalDecision).mockResolvedValue({
      ...decision,
      overall_status: 'PLAN_AT_RISK',
    })
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(screen.getByTestId('badge-overall')).toHaveClass('status-badge--at-risk')
  })

  it('applies feasible CSS class for PLAN_FEASIBLE', async () => {
    vi.mocked(systemApi.health).mockResolvedValue({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    vi.mocked(decisionApi.finalDecision).mockResolvedValue({
      ...decision,
      overall_status: 'PLAN_FEASIBLE',
    })
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(screen.getByTestId('badge-overall')).toHaveClass('status-badge--feasible')
  })

  // Portfolio counts
  it('renders portfolio counts from executive_summary', async () => {
    setupMocks()
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(screen.getByTestId('count-Selected')).toHaveTextContent('12')
    expect(screen.getByTestId('count-Delayed')).toHaveTextContent('3')
    expect(screen.getByTestId('count-No-bid')).toHaveTextContent('1')
    expect(screen.getByTestId('count-Mandatory scheduled')).toHaveTextContent('4')
    expect(screen.getByTestId('count-Mandatory infeasible')).toHaveTextContent('0')
  })

  // Cash values — formatted as JPY
  it('renders EXPECTED scenario ending cash with JPY currency formatting', async () => {
    setupMocks()
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    const expectedCard = screen.getByTestId('cash-scenario-EXPECTED')
    expect(expectedCard).toHaveTextContent(/32,000,000|32.000.000/)
  })

  it('renders DOWNSIDE and SUCCESS ending cash', async () => {
    setupMocks()
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(screen.getByTestId('cash-scenario-DOWNSIDE')).toHaveTextContent(/18,500,000|18.500.000/)
    expect(screen.getByTestId('cash-scenario-SUCCESS')).toHaveTextContent(/47,000,000|47.000.000/)
  })

  // "No breach" when first_buffer_breach_date is null
  it('shows "No breach" when first_buffer_breach_date is null', async () => {
    setupMocks()
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(screen.getByTestId('cash-first-breach')).toHaveTextContent('No breach')
  })

  // Date shown when breach date is present
  it('shows formatted breach date when first_buffer_breach_date is set', async () => {
    vi.mocked(systemApi.health).mockResolvedValue({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    vi.mocked(decisionApi.finalDecision).mockResolvedValue({
      ...decision,
      executive_summary: { ...decision.executive_summary, first_buffer_breach_date: '2031-03-15' },
    })
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    // Should not show "No breach"
    expect(screen.getByTestId('cash-first-breach')).not.toHaveTextContent('No breach')
    // Should include the year
    expect(screen.getByTestId('cash-first-breach')).toHaveTextContent('2031')
  })

  // Key findings
  it('renders risk and strength finding codes', async () => {
    setupMocks()
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(screen.getByTestId('finding-CASH_BUFFER_BREACH')).toBeInTheDocument()
    expect(screen.getByTestId('finding-PLAN_FINANCIALLY_SAFE')).toBeInTheDocument()
  })

  it('shows no-risks/no-strengths fallback when lists are empty', async () => {
    vi.mocked(systemApi.health).mockResolvedValue({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    vi.mocked(decisionApi.finalDecision).mockResolvedValue({
      ...decision,
      executive_summary: { ...decision.executive_summary, major_risks: [], major_strengths: [] },
    })
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(screen.getByText('No major risks identified.')).toBeInTheDocument()
    expect(screen.getByText('No major strengths identified.')).toBeInTheDocument()
  })

  // Future receipts
  it('renders future receipt row', async () => {
    setupMocks()
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(screen.getByTestId('receipt-OPT-001')).toBeInTheDocument()
    expect(screen.getByTestId('receipt-OPT-001')).toHaveTextContent(/8,000,000|8.000.000/)
  })

  it('shows empty-receipts message when future_receipts is empty', async () => {
    vi.mocked(systemApi.health).mockResolvedValue({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    vi.mocked(decisionApi.finalDecision).mockResolvedValue({
      ...decision,
      cash_summary: { ...decision.cash_summary, future_receipts: [] },
    })
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    expect(screen.getByText('No future receipts recorded.')).toBeInTheDocument()
  })

  // Capacity utilisation
  it('renders per-person capacity rows sorted by utilisation desc', async () => {
    setupMocks()
    render(<DashboardPage />)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
    // P001 = 95%, P002 = 50% — P001 should appear first
    const rows = screen.getAllByRole('row')
    const texts = rows.map((r) => r.textContent ?? '')
    const p001idx = texts.findIndex((t) => t.includes('P001'))
    const p002idx = texts.findIndex((t) => t.includes('P002'))
    expect(p001idx).toBeLessThan(p002idx)
  })
})
