import { apiRequest } from './client'
import type { BaselineSummary, HealthResponse } from './types'

export const systemApi = {
  health: () => apiRequest<HealthResponse>('/health'),
  baselineSummary: () => apiRequest<BaselineSummary>('/api/v1/baseline/summary'),
}
