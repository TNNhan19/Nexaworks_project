import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { WorkflowProvider, clearWorkflowForTests, seedWorkflowForTests } from '../workflow/WorkflowContext'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClientError } from '../api/client'
import { baselineCatalogApi, scenarioApi } from '../api/endpoints'
import type { Scenario, ScenarioRun } from '../api/types'
import { ScenariosPage } from './ScenariosPage'

vi.mock('../api/endpoints', () => ({
  scenarioApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn(), run: vi.fn(), runs: vi.fn(), getRun: vi.fn() },
  baselineCatalogApi: { load: vi.fn() },
}))
const scenario: Scenario = {
  id: 'scenario-any-id', name: 'Capacity experiment', description: 'Test assumptions', status: 'ACTIVE',
  created_at: '2032-01-01T00:00:00Z', updated_at: '2032-01-01T00:00:00Z',
  overrides: { people: [], work_items: [], commercial_options: [] },
}
const run = {
  run_id: 'run-arbitrary-900', scenario_id: scenario.id, timestamp: '2032-01-02T10:00:00Z', status: 'COMPLETED',
  final_decision: { overall_status: 'PLAN_FEASIBLE', operational_status: 'OPERATIONALLY_FEASIBLE', financial_status: 'CASH_SAFE' },
  error: null,
} as unknown as ScenarioRun
const catalog = { people: ['PERSON-ZETA-77'], workItems: ['WORK-OMEGA-44'], commercialOptions: ['OFFER-ALPHA-9'] }
function renderPage(entry = '/scenarios') { return render(<MemoryRouter initialEntries={[entry]}><WorkflowProvider><ScenariosPage /></WorkflowProvider></MemoryRouter>) }
describe('ScenariosPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    clearWorkflowForTests()
    seedWorkflowForTests({ status: 'PLAN_GENERATED', source: 'sample', catalog: { summary: { dataset_id: 'TEST' }, company: { name: 'Test', starting_cash_jpy: 12_000_000, fixed_cash_outflow_jpy: 8_000_000, minimum_cash_buffer_jpy: 5_000_000 } } as any, generation: {} as any })
    vi.mocked(scenarioApi.list).mockResolvedValue([scenario])
    vi.mocked(scenarioApi.runs).mockResolvedValue([])
    vi.mocked(baselineCatalogApi.load).mockResolvedValue(catalog)
  })
  it('lists scenarios and historical runs with run navigation', async () => {
    vi.mocked(scenarioApi.runs).mockResolvedValue([run])
    renderPage()
    expect(await screen.findByText('Capacity experiment')).toBeInTheDocument()
    expect(screen.getByText('run-arbitrary-900')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open plan' })).toHaveAttribute('href', '/plan?run_id=run-arbitrary-900')
  })
  it('creates a scenario with dynamically loaded arbitrary IDs', async () => {
    vi.mocked(scenarioApi.create).mockImplementation(async (input) => ({ ...scenario, id: 'created-scenario-id', name: input.name, overrides: input.overrides }))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Create a what-if scenario/ }))
    await userEvent.type(screen.getByLabelText('Scenario name'), 'Arbitrary IDs')
    const people = screen.getByRole('group', { name: 'Team member capacity' })
    await userEvent.click(within(people).getByRole('button', { name: /Add change/ }))
    await userEvent.type(within(people).getByRole('spinbutton'), '123')
    const work = screen.getByRole('group', { name: 'Work effort' })
    await userEvent.click(within(work).getByRole('button', { name: /Add change/ }))
    await userEvent.type(within(work).getByRole('spinbutton'), '45')
    const commercial = screen.getByRole('group', { name: 'Win probability' })
    await userEvent.click(within(commercial).getByRole('button', { name: /Add change/ }))
    await userEvent.type(within(commercial).getByRole('spinbutton'), '72')
    await userEvent.click(screen.getByRole('button', { name: 'Save scenario' }))
    await waitFor(() => expect(scenarioApi.create).toHaveBeenCalled())
    expect(vi.mocked(scenarioApi.create).mock.calls[0][0].overrides).toMatchObject({
      people: [{ person_id: 'PERSON-ZETA-77', capacity_hours: 123 }],
      work_items: [{ work_item_id: 'WORK-OMEGA-44', required_hours: 45 }],
      commercial_options: [{ option_id: 'OFFER-ALPHA-9', estimated_win_probability: 0.72 }],
    })
  })
  it('edits an existing scenario', async () => {
    vi.mocked(scenarioApi.update).mockImplementation(async (_id, input) => ({ ...scenario, ...input }))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    const name = screen.getByLabelText('Scenario name')
    await userEvent.clear(name)
    await userEvent.type(name, 'Edited scenario')
    await userEvent.click(screen.getByRole('button', { name: 'Save scenario' }))
    await waitFor(() => expect(scenarioApi.update).toHaveBeenCalledWith('scenario-any-id', expect.objectContaining({ name: 'Edited scenario' })))
  })
  it('requires explicit confirmation before deletion', async () => {
    vi.mocked(scenarioApi.delete).mockResolvedValue(undefined)
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    expect(scenarioApi.delete).not.toHaveBeenCalled()
    await userEvent.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Delete' }))
    await waitFor(() => expect(scenarioApi.delete).toHaveBeenCalledWith('scenario-any-id'))
    expect(screen.queryByText('Capacity experiment')).not.toBeInTheDocument()
  })
  it('shows client validation errors without calling the backend', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Create a what-if scenario/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Save scenario' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Scenario name is required.')
    expect(scenarioApi.create).not.toHaveBeenCalled()
  })
  it('shows structured backend validation details', async () => {
    vi.mocked(scenarioApi.create).mockRejectedValue(new ApiClientError('Invalid scenario', 400, 'INVALID', ['Capacity conflicts with baseline']))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: /Create a what-if scenario/ }))
    await userEvent.type(screen.getByLabelText('Scenario name'), 'Backend check')
    await userEvent.click(screen.getByRole('button', { name: 'Save scenario' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Capacity conflicts with baseline')
  })
  it('runs a scenario and displays the successful result', async () => {
    vi.mocked(scenarioApi.run).mockResolvedValue(run)
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Analyse scenario' }))
    expect(await screen.findByText('run-arbitrary-900')).toBeInTheDocument()
    expect(screen.getAllByText('Plan is workable')).toHaveLength(2)
  })
  it('shows run failures returned by the API', async () => {
    vi.mocked(scenarioApi.run).mockRejectedValue(new ApiClientError('Scenario run failed', 500))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Analyse scenario' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Scenario run failed')
  })
  it('prefills a cash-adjustment scenario without changing the current plan', async () => {
    vi.mocked(scenarioApi.create).mockImplementation(async (input) => ({ ...scenario, id: 'cash-adjustment', name: input.name, overrides: input.overrides }))
    renderPage('/scenarios?focus=cash&name=Protect+cash&cash_addition=3000000&defer_work=WORK-OMEGA-44&receipt_work=WORK-OMEGA-44&cash_in_days=0')
    expect(await screen.findByDisplayValue('Protect cash')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Save scenario' }))
    await waitFor(() => expect(scenarioApi.create).toHaveBeenCalled())
    expect(vi.mocked(scenarioApi.create).mock.calls[0][0].overrides).toMatchObject({
      company: { starting_cash_jpy: 15000000, fixed_cash_outflow_jpy: 8000000, minimum_cash_buffer_jpy: 5000000 },
      deferred_work_item_ids: ['WORK-OMEGA-44'],
      work_items: [{ work_item_id: 'WORK-OMEGA-44', cash_in_days: 0 }],
    })
  })

})
