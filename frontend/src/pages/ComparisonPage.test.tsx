import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { WorkflowProvider, clearWorkflowForTests, seedWorkflowForTests } from '../workflow/WorkflowContext'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { scenarioApi } from '../api/endpoints'
import type { RunComparison, Scenario, ScenarioRun } from '../api/types'
import { ComparisonPage } from './ComparisonPage'

vi.mock('../api/endpoints', () => ({
  scenarioApi: { list: vi.fn(), runs: vi.fn(), compareRuns: vi.fn() },
}))
const scenarios = [
  { id: 'SC-A', name: 'Baseline case', description: '', status: 'ACTIVE', created_at: '2035-01-01T00:00:00Z', updated_at: '2035-01-01T00:00:00Z', overrides: { people: [], work_items: [], commercial_options: [] } },
  { id: 'SC-B', name: 'Capacity case', description: '', status: 'ACTIVE', created_at: '2035-01-02T00:00:00Z', updated_at: '2035-01-02T00:00:00Z', overrides: { people: [], work_items: [], commercial_options: [] } },
] as Scenario[]
const runs = [
  { run_id: 'RUN-ALPHA-17', scenario_id: 'SC-A', timestamp: '2035-02-01T10:00:00Z', status: 'COMPLETED', error: null },
  { run_id: 'RUN-BETA-93', scenario_id: 'SC-B', timestamp: '2035-02-02T10:00:00Z', status: 'COMPLETED', error: null },
] as unknown as ScenarioRun[]
const comparison: RunComparison = {
  run_a_id: runs[0].run_id, run_b_id: runs[1].run_id,
  status_transition: {
    overall_status: { from: 'PLAN_PARTIAL', to: 'PLAN_FEASIBLE' },
    operational_status: { from: 'OPERATIONALLY_PARTIAL', to: 'OPERATIONALLY_FEASIBLE' },
    financial_status: { from: 'BUFFER_BREACH', to: 'CASH_SAFE' },
  },
  selected: { added: ['ACTION-NEW-99'], removed: ['ACTION-OLD-11'] },
  delayed: { added: [], removed: ['ACTION-DELAYED-4'] },
  no_bid: { added: ['WORK-NO-BID-X'], removed: [] },
  capacity: {
    used_hours: { run_a: 50, run_b: 65, delta: 15 },
    remaining_hours: { run_a: 30, run_b: 15, delta: -15 },
  },
  cash: {
    expected_ending_cash_jpy: { run_a: 9_000_000, run_b: 11_000_000, delta: 2_000_000 },
    downside_ending_cash_jpy: { run_a: 3_000_000, run_b: 4_000_000, delta: 1_000_000 },
    minimum_cash_jpy: { run_a: 2_000_000, run_b: 4_000_000, delta: 2_000_000 },
  },
  buffer_breach: { run_a: true, run_b: false, change: 'RESOLVED' },
  major_risks: { added: ['RISK-NEW-X'], removed: ['RISK-OLD-Y'] },
  major_strengths: { added: ['STRENGTH-NEW-Z'], removed: [] },
}
function renderPage() { return render(<MemoryRouter><WorkflowProvider><ComparisonPage /></WorkflowProvider></MemoryRouter>) }
async function compareRuns() {
  renderPage()
  await screen.findAllByRole('option', { name: /Baseline case/ })
  await userEvent.click(screen.getByRole('button', { name: 'Compare outcomes' }))
}
describe('ComparisonPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    clearWorkflowForTests()
    seedWorkflowForTests({ status: 'PLAN_GENERATED', source: 'sample', catalog: { summary: { dataset_id: 'TEST' } } as any, generation: {} as any })
    vi.mocked(scenarioApi.list).mockResolvedValue(scenarios)
    vi.mocked(scenarioApi.runs).mockImplementation(async (id) => runs.filter((run) => run.scenario_id === id))
    vi.mocked(scenarioApi.compareRuns).mockResolvedValue(comparison)
  })
  it('selects two completed runs and requests their factual comparison', async () => {
    await compareRuns()
    await waitFor(() => expect(scenarioApi.compareRuns).toHaveBeenCalledWith('RUN-ALPHA-17', 'RUN-BETA-93'))
    expect(await screen.findByText('RUN-ALPHA-17')).toBeInTheDocument()
    expect(screen.getByText('RUN-BETA-93')).toBeInTheDocument()
  })
  it('allows an identical-run comparison and explains it without ranking', async () => {
    renderPage()
    const selects = await screen.findAllByRole('combobox')
    await userEvent.selectOptions(selects[1], 'RUN-ALPHA-17')
    expect(screen.getByText(/same run is selected/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Compare outcomes' }))
    await waitFor(() => expect(scenarioApi.compareRuns).toHaveBeenCalledWith('RUN-ALPHA-17', 'RUN-ALPHA-17'))
  })
  it('renders status transitions, cash and capacity deltas', async () => {
    await compareRuns()
    expect(await screen.findByText('Change summary')).toBeInTheDocument()
    expect(screen.getByText('Cash falls below the safety level')).toBeInTheDocument()
    expect(screen.getByText('Cash remains safe')).toBeInTheDocument()
    expect(screen.getAllByText(/2,000,000/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('+15').length).toBeGreaterThan(0)
    expect(screen.getByText('RESOLVED')).toBeInTheDocument()
  })
  it('renders selected, delayed, and NO_BID action changes', async () => {
    await compareRuns()
    expect(await screen.findByText(/ACTION-NEW-99/)).toBeInTheDocument()
    expect(screen.getByText(/ACTION-OLD-11/)).toBeInTheDocument()
    expect(screen.getByText(/ACTION-DELAYED-4/)).toBeInTheDocument()
    expect(screen.getByText(/WORK-NO-BID-X/)).toBeInTheDocument()
  })
  it('renders major risk and strength changes', async () => {
    await compareRuns()
    expect(await screen.findByText(/RISK-NEW-X/)).toBeInTheDocument()
    expect(screen.getByText(/RISK-OLD-Y/)).toBeInTheDocument()
    expect(screen.getByText(/STRENGTH-NEW-Z/)).toBeInTheDocument()
  })
  it('shows comparison API errors', async () => {
    vi.mocked(scenarioApi.compareRuns).mockRejectedValueOnce(new Error('Comparison snapshot unavailable'))
    await compareRuns()
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to connect to the analysis system.')
  })
  it('shows an empty state when no completed runs are available', async () => {
    vi.mocked(scenarioApi.runs).mockResolvedValue([])
    renderPage()
    expect(await screen.findByRole('heading', { name: 'No result to display yet.' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to scenarios' })).toBeInTheDocument()
  })
})
