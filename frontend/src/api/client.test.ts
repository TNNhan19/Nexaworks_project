import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_BASE_URL, ApiClientError, apiRequest } from './client'

afterEach(() => vi.unstubAllGlobals())

describe('apiRequest', () => {
  it('returns typed JSON from the configured backend', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ status: 'ok' }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ))
    vi.stubGlobal('fetch', fetchMock)
    await expect(apiRequest<{ status: string }>('/health')).resolves.toEqual({ status: 'ok' })
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/health`, expect.objectContaining({ headers: expect.objectContaining({ Accept: 'application/json' }) }))
  })

  it('normalizes structured backend errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: 'INVALID_SCENARIO', message: 'Override rejected', errors: ['hours must be positive'] },
    }), { status: 400, statusText: 'Bad Request', headers: { 'Content-Type': 'application/json' } })))
    const error = await apiRequest('/api/v1/scenarios').catch((value: unknown) => value)
    expect(error).toBeInstanceOf(ApiClientError)
    expect(error).toMatchObject({ status: 400, code: 'INVALID_SCENARIO', message: 'Override rejected', details: ['hours must be positive'] })
  })

  it('shows FastAPI 422 field validation instead of only the HTTP status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: [{
        type: 'extra_forbidden',
        loc: ['body', 'overrides', 'deferred_work_item_ids'],
        msg: 'Extra inputs are not permitted',
      }],
    }), { status: 422, statusText: 'Unprocessable Entity', headers: { 'Content-Type': 'application/json' } })))
    const error = await apiRequest('/api/v1/scenarios').catch((value: unknown) => value)
    expect(error).toMatchObject({
      status: 422,
      message: 'Request validation failed.',
      details: ['overrides.deferred_work_item_ids: Extra inputs are not permitted'],
    })
  })

  it('normalizes network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(apiRequest('/health')).rejects.toMatchObject({ status: 0, code: 'NETWORK_ERROR' })
  })
})
