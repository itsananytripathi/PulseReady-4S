import { beforeEach, describe, expect, it, vi } from 'vitest'
import { request } from './client'
import { getHealth } from './endpoints'

describe('typed API client', () => {
  beforeEach(() => { vi.restoreAllMocks(); vi.stubGlobal('fetch', vi.fn()) })

  it('sends the API key only to protected routes and parses JSON', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))
    await request('/healthz', {}, false, { baseUrl: 'http://api', apiKey: 'synthetic-test-key' })
    expect(vi.mocked(fetch).mock.calls[0][1]?.headers).not.toHaveProperty('X-API-Key')
    await request('/api/v1/overview', {}, true, { baseUrl: 'http://api', apiKey: 'synthetic-test-key' })
    expect(new Headers(vi.mocked(fetch).mock.calls[1][1]?.headers).get('X-API-Key')).toBe('synthetic-test-key')
  })

  it('surfaces status and server detail without logging request data', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ detail: 'Invalid API key' }), { status: 401 }))
    await expect(request('/api/v1/overview', {}, true, { baseUrl: 'http://api', apiKey: 'synthetic-test-key' })).rejects.toMatchObject({ status: 401, detail: 'Invalid API key' })
  })

  it('fails clearly when protected configuration is missing', async () => {
    await expect(request('/api/v1/overview', {}, true, { baseUrl: 'http://api' })).rejects.toThrow('VITE_API_KEY')
    expect(fetch).not.toHaveBeenCalled()
  })

  it('handles network failure', async () => {
    vi.mocked(fetch).mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(request('/healthz', {}, false, { baseUrl: 'http://api' })).rejects.toThrow('Failed to fetch')
  })

  it('rejects malformed critical responses', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))
    await expect(getHealth()).rejects.toThrow('Malformed health response')
  })
})
