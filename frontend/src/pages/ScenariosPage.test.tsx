import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
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
function renderPage() { return render(<MemoryRouter><ScenariosPage /></MemoryRouter>) }
describe('ScenariosPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
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
    await userEvent.click(await screen.findByRole('button', { name: 'Create scenario' }))
    await userEvent.type(screen.getByLabelText('Name'), 'Arbitrary IDs')
    const people = screen.getByRole('group', { name: 'Person capacity' })
    await userEvent.click(within(people).getByRole('button', { name: 'Add override' }))
    await userEvent.type(within(people).getByRole('spinbutton'), '123')
    const work = screen.getByRole('group', { name: 'Work required hours' })
    await userEvent.click(within(work).getByRole('button', { name: 'Add override' }))
    await userEvent.type(within(work).getByRole('spinbutton'), '45')
    const commercial = screen.getByRole('group', { name: 'Commercial win probability' })
    await userEvent.click(within(commercial).getByRole('button', { name: 'Add override' }))
    await userEvent.type(within(commercial).getByRole('spinbutton'), '0.72')
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
    const name = screen.getByLabelText('Name')
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
    await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }))
    await waitFor(() => expect(scenarioApi.delete).toHaveBeenCalledWith('scenario-any-id'))
    expect(screen.queryByText('Capacity experiment')).not.toBeInTheDocument()
  })
  it('shows client validation errors without calling the backend', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Create scenario' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save scenario' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Scenario name is required')
    expect(scenarioApi.create).not.toHaveBeenCalled()
  })
  it('shows structured backend validation details', async () => {
    vi.mocked(scenarioApi.create).mockRejectedValue(new ApiClientError('Invalid scenario', 400, 'INVALID', ['Capacity conflicts with baseline']))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Create scenario' }))
    await userEvent.type(screen.getByLabelText('Name'), 'Backend check')
    await userEvent.click(screen.getByRole('button', { name: 'Save scenario' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Capacity conflicts with baseline')
  })
  it('runs a scenario and displays the successful result', async () => {
    vi.mocked(scenarioApi.run).mockResolvedValue(run)
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Run scenario' }))
    expect(await screen.findByText('run-arbitrary-900')).toBeInTheDocument()
    expect(screen.getAllByText('Feasible')).toHaveLength(2)
  })
  it('shows run failures returned by the API', async () => {
    vi.mocked(scenarioApi.run).mockRejectedValue(new ApiClientError('Scenario run failed', 500))
    renderPage()
    await userEvent.click(await screen.findByRole('button', { name: 'Run scenario' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Scenario run failed')
  })
})
