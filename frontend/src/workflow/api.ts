import { apiRequest } from '../api/client'
import type { PlanningCatalog, WorkflowAnalysis, WorkflowGeneration } from './types'

const requestBody = (dataset: Record<string, unknown> | null) =>
  JSON.stringify(dataset ? { dataset } : {})

export const planningApi = {
  sample: () => apiRequest<PlanningCatalog>('/api/v1/planning/sample'),
  review: (dataset: Record<string, unknown>) =>
    apiRequest<PlanningCatalog>('/api/v1/planning/review', {
      method: 'POST',
      body: requestBody(dataset),
    }),
  analyze: (dataset: Record<string, unknown> | null) =>
    apiRequest<WorkflowAnalysis>('/api/v1/planning/analyze', {
      method: 'POST',
      body: requestBody(dataset),
    }),
  generate: (dataset: Record<string, unknown> | null) =>
    apiRequest<WorkflowGeneration>('/api/v1/planning/generate', {
      method: 'POST',
      body: requestBody(dataset),
    }),
}
