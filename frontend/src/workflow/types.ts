import type {
  CashFlowResult,
  CommercialResult,
  FinalDecisionResult,
  PlanResult,
} from '../api/types'

export type WorkflowStatus = 'NO_DATA' | 'DATA_LOADED' | 'ANALYZED' | 'PLAN_GENERATED'
export type PlanningSource = 'sample' | 'uploaded'
export type LocalizedValue = string | { en?: string | null; ja?: string | null; vi?: string | null }

export interface PlanningWorkItem {
  id: string
  title: LocalizedValue
  type: string
  status?: string | null
  mandatory: boolean
  committed?: boolean | null
  customer_id?: string | null
  revenue_jpy: number
  direct_cost_jpy: number
  cash_in_days?: number | null
  success_probability: number
  required_hours: number
  earliest_start: string
  due_date: string
  strategic_value?: number | null
  dependencies: string[]
  conflicts: string[]
  required_languages: string[]
  required_skills: Array<{ skill: string; min_level: number }>
  resource_requirements: Array<{ resource_id: string; hours: number }>
}

export interface PlanningPerson {
  id: string
  person_id?: string
  name: string
  role?: LocalizedValue | null
  capacity_hours: number
  hourly_cost_jpy?: number | null
  skills?: Record<string, number>
  languages?: string[]
  unavailable_ranges?: Array<{ start: string; end: string }>
}

export interface PlanningCustomer {
  id: string
  name: string
  industry?: string | null
}

export interface PlanningCommercialOption {
  work_item_id: string
  option_id: string
  label: LocalizedValue
  price_jpy?: number | null
  delivery_hours?: number | null
  payment_days?: number | null
  estimated_win_probability?: number | null
  dependencies: string[]
}

export interface PlanningCatalog {
  summary: import('../api/types').BaselineSummary
  company: {
    name: string
    starting_cash_jpy: number
    fixed_cash_outflow_jpy: number
    minimum_cash_buffer_jpy: number
  }
  work_items: PlanningWorkItem[]
  people: PlanningPerson[]
  customers: PlanningCustomer[]
  shared_resources: Array<{ id: string; name: LocalizedValue; capacity_hours: number; exclusive?: boolean | null }>
  commercial_options: PlanningCommercialOption[]
  portfolio_effects: Array<{ id: string; trigger: string; targets: string[]; effect: Record<string, unknown> }>
}

export interface WorkflowFinding {
  code: string
  severity: string
  work_item_id?: string
  action_id?: string | null
  details: Record<string, unknown>
}

export interface WorkflowFeasibility {
  work_item_id: string
  status: string
  dependencies: { satisfied: boolean; required: string[]; missing: string[] }
  capacity: { required_hours: number; total_team_capacity_hours: number; sufficient: boolean }
  deadline: { status: string; due_date: string; days_until_due: number }
  hard_failures: WorkflowFinding[]
  blockers: WorkflowFinding[]
  warnings: WorkflowFinding[]
}

export interface WorkflowScoredCandidate {
  action_id: string
  action_type: string
  work_item_id: string
  option_id: string | null
  mandatory: boolean
  selection_status: string
  eligible_for_selection: boolean
  business_value_score: number | null
  reasons: WorkflowFinding[]
  warnings: WorkflowFinding[]
}

export interface WorkflowAnalysis {
  feasibility: WorkflowFeasibility[]
  portfolio: Record<string, unknown>
  commercial: CommercialResult
  scoring: {
    candidates: WorkflowScoredCandidate[]
    score_version: string
    reasons: WorkflowFinding[]
  }
}

export interface WorkflowGeneration extends WorkflowAnalysis {
  plan: PlanResult
  cash_flow: CashFlowResult
  final_decision: FinalDecisionResult
}

export interface WorkflowSnapshot {
  status: WorkflowStatus
  source: PlanningSource | null
  catalog: PlanningCatalog | null
  dataset: Record<string, unknown> | null
  analysis: WorkflowAnalysis | null
  generation: WorkflowGeneration | null
  generatedAt: string | null
}
