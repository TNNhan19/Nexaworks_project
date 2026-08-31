export interface HealthResponse {
  status: string
}

export interface BaselineSummary {
  dataset_id: string
  dataset_version: string
  planning_start: string
  planning_end: string
  currency: string
  starting_cash_jpy: number
  minimum_cash_buffer_jpy: number
  people_count: number
  customer_count: number
  work_item_count: number
  commercial_option_count: number
  shared_resource_count: number
  portfolio_effect_count: number
  total_people_capacity_hours: number
  total_base_work_hours: number
  mandatory_work_count: number
  mandatory_base_hours: number
  work_type_counts: Record<string, number>
}

export interface CompanyOverride {
  starting_cash_jpy?: number
  fixed_cash_outflow_jpy?: number
  minimum_cash_buffer_jpy?: number
}

export interface PersonOverride {
  person_id: string
  capacity_hours?: number
}

export interface WorkItemOverride {
  work_item_id: string
  required_hours?: number
}

export interface CommercialOptionOverride {
  option_id: string
  estimated_win_probability?: number
}

export interface ScenarioOverrides {
  company?: CompanyOverride
  people: PersonOverride[]
  work_items: WorkItemOverride[]
  commercial_options: CommercialOptionOverride[]
  resources?: never[]
}

export interface ScenarioInput {
  name: string
  description: string
  status: 'ACTIVE' | 'INACTIVE'
  overrides: ScenarioOverrides
}

export interface Scenario extends ScenarioInput {
  id: string
  created_at: string
  updated_at: string
}

export interface PlanDecision {
  work_item_id: string
  action_id: string
  decision: string
  selected_option_id: string | null
  prerequisite_ids: string[]
  unlock_trigger_ids: string[]
  reason_codes: string[]
}

export interface Assignment {
  person_id: string
  action_id: string
  assigned_hours: number
  skills_covered: string[]
  languages_covered: string[]
}

export interface ScheduleEntry {
  date: string
  action_id: string
  person_id: string
  hours: number
  allocation_type: string
}

export interface PrerequisiteClosure {
  target_action_id: string
  required_prerequisites: string[]
  unlock_triggers: string[]
  completion_order: string[]
  cycle_detected: boolean
  invalid_references: string[]
}

export interface PersonCapacityUsage {
  person_id: string
  capacity_hours: number
  used_hours: number
  remaining_hours: number
  available_days: number
  daily_capacity_hours: number
}

export interface ResourceCapacityUsage {
  resource_id: string
  capacity_hours: number
  used_hours: number
  remaining_hours: number
  exclusive: boolean
}

export interface PlanResult {
  status: string
  decisions: PlanDecision[]
  prerequisite_closures: PrerequisiteClosure[]
  assignments: Assignment[]
  schedule: ScheduleEntry[]
  selected_actions: string[]
  delayed_actions: string[]
  no_bid_opportunities: string[]
  mandatory_infeasible: string[]
  person_capacity: PersonCapacityUsage[]
  resource_capacity: ResourceCapacityUsage[]
}

export interface CommercialOptionResult {
  option_id: string
  work_item_id: string
  label: string
  availability: string
  deliverability: string
  selectable: boolean
  win_probability: number | null
}

export interface CommercialOpportunityResult {
  work_item_id: string
  title: string
  options: CommercialOptionResult[]
}

export interface CommercialResult {
  opportunities: CommercialOpportunityResult[]
}

export interface ScenarioRun {
  run_id: string
  scenario_id: string
  timestamp: string
  effective_input: Record<string, unknown>
  assumptions: Record<string, unknown>
  feasibility: Record<string, unknown>[]
  portfolio: Record<string, unknown>
  commercial: CommercialResult
  scoring: Record<string, unknown>
  plan: PlanResult
  cash_flow: Record<string, unknown>
  final_decision: FinalDecisionResult
  status: 'COMPLETED' | 'FAILED'
  error: { code?: string; message?: string } | null
}

export interface BaselineCatalog {
  people: string[]
  workItems: string[]
  commercialOptions: string[]
}

export interface StructuredErrorDetail {
  code?: string
  message?: string
  errors?: string[]
}

// ---------------------------------------------------------------------------
// Phase 5B — FinalDecisionResult types (mirrors Phase 2G Pydantic models)
// ---------------------------------------------------------------------------

export type OverallStatus =
  | 'PLAN_FEASIBLE'
  | 'PLAN_PARTIAL'
  | 'PLAN_AT_RISK'
  | 'PLAN_INFEASIBLE'

export type OperationalStatus =
  | 'OPERATIONALLY_FEASIBLE'
  | 'OPERATIONALLY_PARTIAL'
  | 'OPERATIONALLY_AT_RISK'
  | 'OPERATIONALLY_INFEASIBLE'

export type FinancialStatus =
  | 'CASH_SAFE'
  | 'CASH_AT_RISK'
  | 'BUFFER_BREACH'
  | 'NEGATIVE_CASH'

export type FindingSeverity = 'CRITICAL' | 'ERROR' | 'WARNING' | 'INFO'
export type SourcePhase =
  | 'FEASIBILITY'
  | 'PORTFOLIO'
  | 'COMMERCIAL'
  | 'SCORING'
  | 'PLANNER'
  | 'CASH_FLOW'
  | 'FINAL_VALIDATION'

export interface ExplanationRecord {
  code: string
  severity: FindingSeverity
  source_phase: SourcePhase
  source_id: string | null
  action_id: string | null
  evidence: Record<string, unknown>
}

export interface ExecutiveSummary {
  plan_status: string
  operational_status: string
  financial_status: string
  selected_count: number
  delayed_count: number
  no_bid_count: number
  mandatory_total: number
  mandatory_scheduled_count: number
  mandatory_infeasible_count: number
  total_capacity_hours: number
  total_used_hours: number
  total_remaining_hours: number
  expected_ending_cash_jpy: number | null
  downside_ending_cash_jpy: number | null
  success_ending_cash_jpy: number | null
  minimum_cash_jpy: number | null
  minimum_cash_date: string | null
  first_buffer_breach_date: string | null
  major_risks: string[]
  major_strengths: string[]
}

export interface MandatoryItemOutcome {
  work_item_id: string
  scheduled: boolean
  infeasible: boolean
  omitted: boolean
  prerequisite_ids: string[]
  completion_date: string | null
}

export interface MandatorySummary {
  total_mandatory: number
  scheduled_count: number
  infeasible_count: number
  omitted_count: number
  outcomes: MandatoryItemOutcome[]
}

export interface PersonCapacitySummary {
  person_id: string
  capacity_hours: number
  used_hours: number
  remaining_hours: number
  utilisation_pct: number
}

export interface CapacitySummary {
  total_capacity_hours: number
  total_used_hours: number
  total_remaining_hours: number
  people: PersonCapacitySummary[]
  violations: ExplanationRecord[]
}

export interface ResourceUsageSummary {
  resource_id: string
  capacity_hours: number
  used_hours: number
  remaining_hours: number
  exclusive: boolean
  utilisation_pct: number
}

export interface ResourceSummary {
  resources: ResourceUsageSummary[]
  violations: ExplanationRecord[]
}

export interface ScenarioCashSummary {
  scenario: string
  status: string
  ending_cash_jpy: number
  minimum_cash_jpy: number
  minimum_cash_date: string
  first_buffer_breach_date: string | null
  days_below_buffer: number
  negative_cash: boolean
}

export interface FutureReceiptSummary {
  source_id: string
  event_type: string
  date: string
  expected_amount_jpy: number
}

export interface CashSummary {
  starting_cash_jpy: number
  minimum_buffer_jpy: number
  financial_status: FinancialStatus
  scenarios: ScenarioCashSummary[]
  future_receipts: FutureReceiptSummary[]
  findings: ExplanationRecord[]
}

export interface FinalDecisionResult {
  overall_status: OverallStatus
  operational_status: OperationalStatus
  financial_status: FinancialStatus
  executive_summary: ExecutiveSummary
  mandatory_summary: MandatorySummary
  capacity_summary: CapacitySummary
  resource_summary?: ResourceSummary
  cash_summary: CashSummary
  decision_explanations: unknown[]
  validations: ExplanationRecord[]
  warnings: ExplanationRecord[]
  critical_issues: ExplanationRecord[]
  explanation_records: ExplanationRecord[]
  source_versions: Record<string, string>
  assumptions_used: Record<string, unknown>
}
