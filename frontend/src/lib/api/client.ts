import { ApiError } from './errors'

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export interface ApiConfig {
  baseUrl: string
  apiKey?: string
}

export function getApiConfig(): ApiConfig {
  return {
    baseUrl: (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(/\/$/, ''),
    apiKey: import.meta.env.VITE_API_KEY || undefined,
  }
}

export function requireApiKey(config = getApiConfig()): string {
  if (!config.apiKey) throw new ApiError('VITE_API_KEY is not configured for this frontend.', null, 'Configure VITE_API_KEY.')
  return config.apiKey
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
  protectedRoute = true,
  config = getApiConfig(),
): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 12_000)
  const signal = options.signal ? AbortSignal.any([options.signal, controller.signal]) : controller.signal
  const headers = new Headers(options.headers)
  if (protectedRoute) headers.set('X-API-Key', requireApiKey(config))
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  try {
    const response = await fetch(`${config.baseUrl}${path}`, { ...options, headers, signal })
    const text = await response.text()
    let body: unknown = undefined
    if (text) {
      try { body = JSON.parse(text) } catch { body = text }
    }
    if (!response.ok) {
      const detail = typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : typeof body === 'string' ? body : `HTTP ${response.status}`
      throw new ApiError(`Request failed with status ${response.status}`, response.status, detail)
    }
    return body as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('The request timed out.', null, 'Request timed out.')
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

export async function requestBlob(
  path: string,
  options: RequestInit = {},
  protectedRoute = true,
  config = getApiConfig(),
): Promise<Blob> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 12_000)
  const signal = options.signal ? AbortSignal.any([options.signal, controller.signal]) : controller.signal
  const headers = new Headers(options.headers)
  if (protectedRoute) headers.set('X-API-Key', requireApiKey(config))
  try {
    const response = await fetch(`${config.baseUrl}${path}`, { ...options, headers, signal })
    if (!response.ok) {
      const text = await response.text()
      let detail = `HTTP ${response.status}`
      try {
        const body = JSON.parse(text) as { detail?: unknown }
        if (body && typeof body.detail !== 'undefined') detail = String(body.detail)
      } catch { if (text) detail = text }
      throw new ApiError(`Request failed with status ${response.status}`, response.status, detail)
    }
    return await response.blob()
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError('The request timed out.', null, 'Request timed out.')
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}
