/**
 * The one way the app calls the backend: the `openapi-fetch` client typed by the generated
 * `schema.d.ts`, and `api()`, which returns a call's data or throws an `ApiError`.
 *
 *   const health = await api(client.GET('/api/health'))
 *
 * Requests go to the page's own origin (Vite proxies `/api` to the backend), send cookies, and
 * use JSON bodies only.
 */
import createClient, { type ClientOptions } from 'openapi-fetch'

import type { components, paths } from './schema'

export type ErrorBody = components['schemas']['ErrorBody']

/** Codes the client produces itself, when there is no standard error body to read. */
export const NETWORK_ERROR = 'network_error'
export const UNEXPECTED_RESPONSE = 'unexpected_response'

/**
 * A failed call. `code` is the server's error code (branch on it, never on `message`), or
 * `network_error` when the API couldn't be reached, or `unexpected_response` when it answered
 * with something other than the standard `{code, message, details}` body. `status` is the
 * response's status, or 0 when there was none, or when a success's body couldn't be read.
 */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, body: ErrorBody) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.details = body.details
  }
}

export function createApiClient(options: ClientOptions = {}) {
  return createClient<paths>({
    baseUrl: globalThis.location?.origin,
    credentials: 'include',
    headers: { Accept: 'application/json' },
    ...options,
  })
}

export const client = createApiClient()

function isErrorBody(value: unknown): value is ErrorBody {
  if (typeof value !== 'object' || value === null) return false
  const body = value as Record<string, unknown>
  return (
    typeof body.code === 'string' &&
    typeof body.message === 'string' &&
    typeof body.details === 'object' &&
    body.details !== null
  )
}

type Result<T> = { data?: T; error?: unknown; response: Response }

// What the Vite proxy (or, in production, a reverse proxy) answers, without a standard body,
// when the API behind it is down or not answering.
const GATEWAY_STATUSES = new Set([502, 503, 504])

const UNREACHABLE: ErrorBody = {
  code: NETWORK_ERROR,
  message: 'Could not reach the server. Check your connection and try again.',
  details: {},
}

/** Await a client call: its data on success, or an `ApiError` thrown on any failure. */
export async function api<T>(call: Promise<Result<T>>): Promise<T> {
  let result: Result<T>
  try {
    result = await call
  } catch (cause) {
    if (cause instanceof SyntaxError) {
      // A success status with a body that isn't JSON.
      throw new ApiError(0, {
        code: UNEXPECTED_RESPONSE,
        message: 'The server sent a response the app could not read.',
        details: {},
      })
    }
    // fetch rejects with a TypeError when it can't connect. Anything else (a cancelled request,
    // a bug while building one) is not the network's fault: let it surface as it is.
    if (cause instanceof TypeError) throw new ApiError(0, UNREACHABLE)
    throw cause
  }
  const { data, error, response } = result
  if (response.ok) return data as T
  if (isErrorBody(error)) throw new ApiError(response.status, error)
  if (GATEWAY_STATUSES.has(response.status)) throw new ApiError(response.status, UNREACHABLE)
  throw new ApiError(response.status, {
    code: UNEXPECTED_RESPONSE,
    message: `The server answered with an unexpected error (${response.status}).`,
    details: {},
  })
}
