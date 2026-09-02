import { apiRequest } from './client'
import type {
  BaselineCatalog,
  BaselineSummary,
  CommercialResult,
  FinalDecisionResult,
  HealthResponse,
  PlanResult,
  Scenario,
  ScenarioInput,
  ScenarioRun,
  RunComparison,
} from './types'

export const systemApi = {
  health: () => apiRequest<HealthResponse>('/health'),
  baselineSummary: () => apiRequest<BaselineSummary>('/api/v1/baseline/summary'),
}

export const decisionApi = {
  /** Runs the full Phase 2E→2F→2G pipeline on the canonical dataset. */
  finalDecision: () =>
    apiRequest<FinalDecisionResult>('/api/v1/final-decision', {
      method: 'POST',
      body: JSON.stringify({}),
    }),
}

export const scenarioApi = {
  list: () => apiRequest<Scenario[]>('/api/v1/scenarios'),
  create: (input: ScenarioInput) => apiRequest<Scenario>('/api/v1/scenarios', {
    method: 'POST', body: JSON.stringify(input),
  }),
  update: (id: string, input: ScenarioInput) => apiRequest<Scenario>(`/api/v1/scenarios/${encodeURIComponent(id)}`, {
    method: 'PATCH', body: JSON.stringify(input),
  }),
  delete: (id: string) => apiRequest<void>(`/api/v1/scenarios/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  run: (id: string) => apiRequest<ScenarioRun>(`/api/v1/scenarios/${encodeURIComponent(id)}/run`, { method: 'POST' }),
  runs: (id: string) => apiRequest<ScenarioRun[]>(`/api/v1/scenarios/${encodeURIComponent(id)}/runs`),
  getRun: (runId: string) => apiRequest<ScenarioRun>(`/api/v1/runs/${encodeURIComponent(runId)}`),
  compareRuns: (runAId: string, runBId: string) => {
    const query = new URLSearchParams({ run_a_id: runAId, run_b_id: runBId })
    return apiRequest<RunComparison>(`/api/v1/runs/compare?${query.toString()}`)
  },
}

export const baselineCatalogApi = {
  load: async (): Promise<BaselineCatalog> => {
    const [plan, commercial] = await Promise.all([
      apiRequest<PlanResult>('/api/v1/plan'),
      apiRequest<CommercialResult>('/api/v1/commercial'),
    ])
    return {
      people: [...new Set(plan.person_capacity.map((item) => item.person_id))],
      workItems: [...new Set(plan.decisions.map((item) => item.work_item_id))],
      commercialOptions: [...new Set(commercial.opportunities.flatMap((item) => item.options.map((option) => option.option_id)))],
    }
  },
}

export const workforceApi = {
  getPeople: () => apiRequest<import('../workflow/types').PlanningPerson[]>('/api/v1/workforce/people'),
}
