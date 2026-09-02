import type { StructuredErrorDetail } from './types'

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''
export const API_BASE_URL = configuredBaseUrl.replace(/\/$/, '')

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string
  readonly details: string[]

  constructor(message: string, status: number, code = 'API_ERROR', details: string[] = []) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
    this.details = details
  }
}

type FastApiValidationError = { loc?: Array<string | number>; msg?: string; type?: string }

function validationDetails(detail: unknown): string[] {
  if (!Array.isArray(detail)) return []
  return detail.map((item: unknown) => {
    if (!item || typeof item !== 'object') return String(item)
    const validation = item as FastApiValidationError
    const location = validation.loc?.filter((part) => part !== 'body').join('.')
    const message = validation.msg ?? validation.type ?? 'Invalid value'
    return location ? `${location}: ${message}` : message
  })
}

async function parseError(response: Response): Promise<ApiClientError> {
  let body: { detail?: StructuredErrorDetail | string | FastApiValidationError[] } | undefined
  try {
    body = await response.json() as typeof body
  } catch {
    return new ApiClientError(response.statusText || 'Request failed', response.status)
  }
  const detail = body?.detail
  if (typeof detail === 'string') {
    return new ApiClientError(detail, response.status)
  }
  if (Array.isArray(detail)) {
    return new ApiClientError(
      response.status === 422 ? 'Request validation failed.' : (response.statusText || 'Request failed'),
      response.status,
      'VALIDATION_ERROR',
      validationDetails(detail),
    )
  }
  return new ApiClientError(
    detail?.message ?? response.statusText ?? 'Request failed',
    response.status,
    detail?.code,
    detail?.errors,
  )
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...init.headers,
      },
    })
  } catch (error) {
    throw new ApiClientError(
      error instanceof Error ? error.message : 'Unable to reach the backend',
      0,
      'NETWORK_ERROR',
    )
  }
  if (!response.ok) {
    throw await parseError(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}
