export class ApiError extends Error {
  readonly status: number | null
  readonly detail: string

  constructor(message: string, status: number | null = null, detail = message) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export function safeErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Authentication was rejected. Check the local demo API key.'
    if (error.status === 403) return 'This API key is not provisioned for a tenant.'
    if (error.status === 404) return 'The requested record or facility was not found.'
    if (error.status === 409) return error.detail || 'The operation conflicts with the current server state.'
    if (error.status === 413) return 'The upload exceeds the server size limit.'
    if (error.status === 415) return 'Upload a CSV or JSON file.'
    if (error.status === 422) return error.detail || 'The server rejected the submitted values.'
    return error.detail || 'The backend returned an error.'
  }
  if (error instanceof Error && error.message === 'Failed to fetch') {
    return 'The backend is unreachable. Check that FastAPI is running and retry.'
  }
  return 'The request could not be completed. Retry when the backend is available.'
}
