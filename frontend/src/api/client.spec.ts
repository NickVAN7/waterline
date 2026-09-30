import { describe, expect, it, vi } from 'vitest'

import { api, ApiError, createApiClient } from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** A client whose fetch answers with `response` (or rejects with it) and records the request. */
function clientAnswering(response: Response | Error) {
  const requests: Request[] = []
  const fetch = vi.fn(async (request: Request) => {
    requests.push(request)
    if (response instanceof Error) throw response
    return response
  })
  return { client: createApiClient({ fetch }), requests }
}

async function failure(call: Promise<unknown>): Promise<ApiError> {
  const error: unknown = await call.catch((e: unknown) => e)
  expect(error).toBeInstanceOf(ApiError)
  return error as ApiError
}

describe('requests', () => {
  it('go to the page origin, send cookies, and ask for JSON', async () => {
    const { client, requests } = clientAnswering(
      jsonResponse(200, { status: 'ok', database: 'ok' }),
    )

    await api(client.GET('/api/health'))

    const [request] = requests
    expect(request?.url).toBe(`${window.location.origin}/api/health`)
    expect(request?.credentials).toBe('include')
    expect(request?.headers.get('Accept')).toBe('application/json')
  })
})

describe('api()', () => {
  it('returns the response data on success', async () => {
    const { client } = clientAnswering(jsonResponse(200, { status: 'ok', database: 'ok' }))

    await expect(api(client.GET('/api/health'))).resolves.toEqual({ status: 'ok', database: 'ok' })
  })

  it('throws the standard error body as an ApiError with its status, code, and details', async () => {
    const { client } = clientAnswering(
      jsonResponse(503, {
        code: 'service_unavailable',
        message: 'The database is unavailable.',
        details: { database: 'unavailable' },
      }),
    )

    const error = await failure(api(client.GET('/api/health')))

    expect(error.status).toBe(503)
    expect(error.code).toBe('service_unavailable')
    expect(error.message).toBe('The database is unavailable.')
    expect(error.details).toEqual({ database: 'unavailable' })
  })

  it.each([
    ['an HTML error page', new Response('<h1>Internal Server Error</h1>', { status: 500 })],
    ['JSON without the standard fields', jsonResponse(500, { detail: 'boom' })],
    ['a body with no details', jsonResponse(500, { code: 'x', message: 'y' })],
    ['a JSON null', jsonResponse(500, null)],
  ])('reports %s as unexpected_response with the status', async (_case, response) => {
    const { client } = clientAnswering(response)

    const error = await failure(api(client.GET('/api/health')))

    expect(error.status).toBe(response.status)
    expect(error.code).toBe('unexpected_response')
    expect(error.message).toBe(`The server answered with an unexpected error (${response.status}).`)
  })

  it('reports a success whose body is not JSON as unexpected_response', async () => {
    const { client } = clientAnswering(new Response('<html></html>', { status: 200 }))

    const error = await failure(api(client.GET('/api/health')))

    expect(error.code).toBe('unexpected_response')
    expect(error.status).toBe(0)
  })

  it.each([
    ['an empty 502 (the proxy with the API down)', new Response(null, { status: 502 })],
    ['a 503 page', new Response('<h1>Service Unavailable</h1>', { status: 503 })],
    ['an empty 504 (the API not answering)', new Response(null, { status: 504 })],
  ])('reports %s as network_error with the status', async (_case, response) => {
    const { client } = clientAnswering(response)

    const error = await failure(api(client.GET('/api/health')))

    expect(error.code).toBe('network_error')
    expect(error.status).toBe(response.status)
    expect(error.message).toBe('Could not reach the server. Check your connection and try again.')
  })

  it('lets any other failure through unchanged instead of blaming the network', async () => {
    const bug = new RangeError('bug while building the request')
    const { client } = clientAnswering(bug)

    await expect(api(client.GET('/api/health'))).rejects.toBe(bug)
  })

  it('reports an unreachable server as network_error with status 0', async () => {
    const { client } = clientAnswering(new TypeError('Failed to fetch'))

    const error = await failure(api(client.GET('/api/health')))

    expect(error.code).toBe('network_error')
    expect(error.status).toBe(0)
    expect(error.message).toBe('Could not reach the server. Check your connection and try again.')
  })
})
