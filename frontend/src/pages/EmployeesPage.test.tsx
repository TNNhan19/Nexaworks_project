import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { EmployeesPage } from './EmployeesPage'
import { WorkflowProvider, clearWorkflowForTests, seedWorkflowForTests } from '../workflow/WorkflowContext'

const mockPeople = [
  {
    id: 'EMP-001',
    name: 'Nguyen Van A',
    role: { en: 'Tech Lead', vi: 'Trưởng nhóm kỹ thuật', ja: 'テックリード' },
    capacity_hours: 160,
    hourly_cost_jpy: 5000,
    skills: { backend: 5, ai: 4 },
    languages: ['vi', 'en'],
    unavailable_ranges: [{ start: '2026-10-10', end: '2026-10-12' }],
  },
  {
    id: 'EMP-002',
    name: 'Sato Kenji',
    role: { en: 'Frontend Engineer', vi: 'Kỹ sư Frontend', ja: 'フロントエンド' },
    capacity_hours: 140,
    hourly_cost_jpy: 4500,
    skills: { frontend: 5, ui_design: 4 },
    languages: ['ja', 'en'],
    unavailable_ranges: [],
  },
]

const mockCatalog = {
  summary: { dataset_id: 'TEST-DS', currency: 'JPY' },
  company: { name: 'Test Co', starting_cash_jpy: 10000000, minimum_cash_buffer_jpy: 1000000 },
  people: mockPeople,
  work_items: [
    {
      id: 'W-101',
      title: { en: 'Core API Optimization', vi: 'Tối ưu API' },
      required_hours: 40,
      mandatory: true,
      due_date: '2026-10-25',
      dependencies: [],
    },
  ],
  customers: [],
  shared_resources: [],
  commercial_options: [],
  portfolio_effects: [],
} as any

const mockGeneration = {
  plan: {
    status: 'FEASIBLE',
    decisions: [],
    selected_actions: ['W-101'],
    delayed_actions: [],
    no_bid_opportunities: [],
    mandatory_infeasible: [],
    assignments: [
      {
        person_id: 'EMP-001',
        action_id: 'W-101',
        assigned_hours: 40,
        assignment_role: 'OWNER',
        skills_covered: ['backend'],
        languages_covered: ['vi'],
      },
    ],
    schedule: [],
    person_capacity: [],
    resource_capacity: [],
  },
  final_decision: {
    overall_status: 'PLAN_FEASIBLE',
    operational_status: 'OPERATIONALLY_FEASIBLE',
    financial_status: 'CASH_SAFE',
    executive_summary: {},
    mandatory_summary: { total_mandatory: 1, scheduled_count: 1, infeasible_count: 0, omitted_count: 0 },
    capacity_summary: {
      total_capacity_hours: 300,
      total_used_hours: 40,
      total_remaining_hours: 260,
      people: [
        {
          person_id: 'EMP-001',
          capacity_hours: 160,
          used_hours: 40,
          remaining_hours: 120,
          utilisation_pct: 25,
        },
        {
          person_id: 'EMP-002',
          capacity_hours: 140,
          used_hours: 0,
          remaining_hours: 140,
          utilisation_pct: 0,
        },
      ],
    },
    cash_summary: { scenarios: [] },
  },
} as any

describe('EmployeesPage', () => {
  beforeEach(() => {
    clearWorkflowForTests()
  })

  it('renders employee master data and statistics', () => {
    seedWorkflowForTests({
      status: 'PLAN_GENERATED',
      source: 'sample',
      catalog: mockCatalog,
      generation: mockGeneration,
    })

    render(
      <MemoryRouter>
        <WorkflowProvider>
          <EmployeesPage />
        </WorkflowProvider>
      </MemoryRouter>
    )

    expect(screen.getByText('Nguyen Van A')).toBeInTheDocument()
    expect(screen.getByText('Sato Kenji')).toBeInTheDocument()
    expect(screen.getByText('EMP-001')).toBeInTheDocument()
    expect(screen.getByText('EMP-002')).toBeInTheDocument()
    expect(screen.getByText('300h')).toBeInTheDocument()
  })

  it('filters employees by search term', async () => {
    seedWorkflowForTests({
      status: 'DATA_LOADED',
      source: 'sample',
      catalog: mockCatalog,
    })

    render(
      <MemoryRouter>
        <WorkflowProvider>
          <EmployeesPage />
        </WorkflowProvider>
      </MemoryRouter>
    )

    const searchInput = screen.getByRole('textbox')
    await userEvent.type(searchInput, 'Kenji')

    expect(screen.getByText('Sato Kenji')).toBeInTheDocument()
    expect(screen.queryByText('Nguyen Van A')).not.toBeInTheDocument()
  })

  it('opens employee detail modal on click with assignments and skills', async () => {
    seedWorkflowForTests({
      status: 'PLAN_GENERATED',
      source: 'sample',
      catalog: mockCatalog,
      generation: mockGeneration,
    })

    render(
      <MemoryRouter>
        <WorkflowProvider>
          <EmployeesPage />
        </WorkflowProvider>
      </MemoryRouter>
    )

    const card = screen.getByTestId('employee-card-EMP-001')
    await userEvent.click(card)

    expect(screen.getByTestId('employee-detail-modal')).toBeInTheDocument()
    expect(screen.getByText('Core API Optimization')).toBeInTheDocument()
    expect(screen.getByText('40h')).toBeInTheDocument()
    expect(screen.getByText('¥5,000 / h')).toBeInTheDocument()

    // Close modal
    const closeBtn = screen.getByRole('button', { name: 'Close' })
    await userEvent.click(closeBtn)
    expect(screen.queryByTestId('employee-detail-modal')).not.toBeInTheDocument()
  })

  it('handles dataset gracefully when no plan is generated yet', () => {
    seedWorkflowForTests({
      status: 'DATA_LOADED',
      source: 'sample',
      catalog: mockCatalog,
    })

    render(
      <MemoryRouter>
        <WorkflowProvider>
          <EmployeesPage />
        </WorkflowProvider>
      </MemoryRouter>
    )

    expect(screen.getByText('Nguyen Van A')).toBeInTheDocument()
    expect(screen.getByText('0.0%')).toBeInTheDocument()
  })
})
