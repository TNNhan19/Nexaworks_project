import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DashboardPage } from './DashboardPage'
import { systemApi, decisionApi } from '../api/endpoints'
import type { FinalDecisionResult } from '../api/types'

vi.mock('../api/endpoints', () => ({
  systemApi: { health: vi.fn(), baselineSummary: vi.fn() },
  decisionApi: { finalDecision: vi.fn() },
}))

const baseline = {
  dataset_id: 'DYNAMIC-DATASET', dataset_version: '9.4', planning_start: '2031-02-03', planning_end: '2031-02-28', currency: 'JPY',
  starting_cash_jpy: 12_345_678, minimum_cash_buffer_jpy: 4_321_000,
  people_count: 13, customer_count: 4, work_item_count: 37, commercial_option_count: 2,
  shared_resource_count: 3, portfolio_effect_count: 1, total_people_capacity_hours: 912.5,
  total_base_work_hours: 1200, mandatory_work_count: 8, mandatory_base_hours: 420,
  work_type_counts: { delivery: 37 },
}

/** Minimal valid FinalDecisionResult for legacy tests that only care about baseline metadata */
const minimalDecision: FinalDecisionResult = {
  overall_status: 'PLAN_PARTIAL',
  operational_status: 'OPERATIONALLY_PARTIAL',
  financial_status: 'CASH_SAFE',
  executive_summary: {
    plan_status: 'PLAN_PARTIAL', operational_status: 'OPERATIONALLY_PARTIAL', financial_status: 'CASH_SAFE',
    selected_count: 5, delayed_count: 1, no_bid_count: 0,
    mandatory_total: 2, mandatory_scheduled_count: 2, mandatory_infeasible_count: 0,
    total_capacity_hours: 912.5, total_used_hours: 400, total_remaining_hours: 512.5,
    expected_ending_cash_jpy: 10_000_000, downside_ending_cash_jpy: 8_000_000, success_ending_cash_jpy: 12_000_000,
    minimum_cash_jpy: 7_000_000, minimum_cash_date: '2031-02-20', first_buffer_breach_date: null,
    major_risks: [], major_strengths: [],
  },
  mandatory_summary: { total_mandatory: 2, scheduled_count: 2, infeasible_count: 0, omitted_count: 0, outcomes: [] },
  capacity_summary: { total_capacity_hours: 912.5, total_used_hours: 400, total_remaining_hours: 512.5, people: [], violations: [] },
  cash_summary: {
    starting_cash_jpy: 12_345_678, minimum_buffer_jpy: 4_321_000, financial_status: 'CASH_SAFE',
    scenarios: [
      { scenario: 'EXPECTED', status: 'CASH_SAFE', ending_cash_jpy: 10_000_000, minimum_cash_jpy: 7_000_000, minimum_cash_date: '2031-02-20', first_buffer_breach_date: null, days_below_buffer: 0, negative_cash: false },
    ],
    future_receipts: [], findings: [],
  },
  decision_explanations: [], validations: [], warnings: [], critical_issues: [], explanation_records: [],
  source_versions: {}, assumptions_used: {},
}

describe('DashboardPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows a loading state while backend calls are pending', () => {
    vi.mocked(systemApi.health).mockReturnValue(new Promise(() => undefined))
    vi.mocked(systemApi.baselineSummary).mockReturnValue(new Promise(() => undefined))
    vi.mocked(decisionApi.finalDecision).mockReturnValue(new Promise(() => undefined))
    render(<DashboardPage />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading baseline data')
  })

  it('shows a structured error and retries', async () => {
    vi.mocked(systemApi.health).mockRejectedValueOnce(new Error('Backend unavailable')).mockResolvedValueOnce({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    vi.mocked(decisionApi.finalDecision).mockResolvedValue(minimalDecision)
    render(<DashboardPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Backend unavailable')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    expect(systemApi.health).toHaveBeenCalledTimes(2)
  })

  it('renders baseline values returned by the API without canonical constants', async () => {
    vi.mocked(systemApi.health).mockResolvedValue({ status: 'ok' })
    vi.mocked(systemApi.baselineSummary).mockResolvedValue(baseline)
    vi.mocked(decisionApi.finalDecision).mockResolvedValue(minimalDecision)
    render(<DashboardPage />)
    expect(await screen.findByText('Connected')).toBeInTheDocument()
    // baseline metric strip still shows people_count and work_item_count
    expect(screen.getByText('13')).toBeInTheDocument()
    expect(screen.getByText('37')).toBeInTheDocument()
    // cash section shows EXPECTED ending cash from minimalDecision
    expect(screen.getByTestId('cash-scenario-EXPECTED')).toHaveTextContent(/10,000,000|10.000.000/)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
  })

})
