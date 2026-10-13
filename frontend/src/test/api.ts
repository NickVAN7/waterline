/** Typed results for the mocked API client in component tests (`vi.spyOn(client, 'GET')`). */
import type { ErrorBody } from '@/api/client'
import type { Me } from '@/stores/currentUser'

// The client's result type, for `mockResolvedValue`; the payloads are typed from the schema.
type Result = never

export function ok<T>(data: T, status = 200): Result {
  return { data, response: new Response(null, { status }) } as never
}

export function noContent(): Result {
  return { data: undefined, response: new Response(null, { status: 204 }) } as never
}

export function failed(status: number, body: ErrorBody): Result {
  return { error: body, response: new Response(null, { status }) } as never
}

export function validationFailed(
  fields: { loc: (string | number)[]; message: string; type: string }[],
): Result {
  return failed(422, {
    code: 'validation_error',
    message: 'Check the highlighted fields.',
    details: { fields },
  })
}

export function me(overrides: Partial<Me> = {}): Me {
  return {
    user: {
      id: '0190f0a0-0000-7000-8000-000000000001',
      email: 'casey@harbor.example',
      username: 'casey',
      name: 'Casey Cole',
    },
    is_system_admin: false,
    must_change_password: false,
    workspaces: [],
    orgs: [],
    ...overrides,
  }
}
