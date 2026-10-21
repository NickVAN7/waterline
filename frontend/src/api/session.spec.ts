import { describe, expect, it, vi } from 'vitest'

import { onSessionProblem, sessionMiddleware, type SessionProblem } from './client'

function respond(path: string, status: number, body?: unknown) {
  const request = new Request(`http://localhost${path}`)
  const response = new Response(body === undefined ? null : JSON.stringify(body), { status })
  return sessionMiddleware.onResponse!({ request, response } as never)
}

function listen() {
  const problems: SessionProblem[] = []
  const handler = vi.fn((problem: SessionProblem) => problems.push(problem))
  onSessionProblem(handler)
  return problems
}

describe('session problems from responses', () => {
  it('reports a 401 as an ended session', async () => {
    const problems = listen()

    await respond('/api/me/work', 401, { code: 'not_authenticated', message: 'x', details: {} })

    expect(problems).toEqual(['session_ended'])
  })

  it('does not report a failed sign-in, which is also 401', async () => {
    const problems = listen()

    await respond('/api/auth/sign-in', 401, {
      code: 'invalid_credentials',
      message: 'x',
      details: {},
    })

    expect(problems).toEqual([])
  })

  it('reports a 403 password_change_required', async () => {
    const problems = listen()

    await respond('/api/me/work', 403, {
      code: 'password_change_required',
      message: 'x',
      details: {},
    })

    expect(problems).toEqual(['password_change_required'])
  })

  it.each([
    ['another 403', 403, { code: 'forbidden', message: 'x', details: {} }],
    ['a 403 with no standard body', 403, 'not json'],
    ['a success', 200, { ok: true }],
  ])('ignores %s', async (_name, status, body) => {
    const problems = listen()

    await respond('/api/me/work', status, body)

    expect(problems).toEqual([])
  })
})
