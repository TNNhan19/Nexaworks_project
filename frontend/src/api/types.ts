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

export interface StructuredErrorDetail {
  code?: string
  message?: string
  errors?: string[]
}
