/** Typed results for the mocked API client in component tests (`vi.spyOn(client, 'GET')`). */
import type { ErrorBody } from '@/api/client'
import type { components } from '@/api/schema'
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

export const ACME: Me['orgs'][number] = {
  id: '0190f0a0-0000-7000-8000-0000000000a1',
  name: 'Acme Manufacturing',
  slug: 'acme',
  role: 'member',
  allowed_actions: [],
}

/** A signed-in user, a member of one org (`ACME`) unless the overrides say otherwise. */
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
    orgs: [ACME],
    ...overrides,
  }
}

/** `GET /api/auth/password-policy` as the server sends it (DL-91, DL-94). */
export const PASSWORD_POLICY = {
  requirements: [
    { code: 'too_short', label: 'At least 8 characters', value: 8 },
    { code: 'same_as_email', label: 'Not your email', value: null },
    { code: 'same_as_username', label: 'Not your username', value: null },
    { code: 'same_as_current', label: 'Not your current password', value: null },
  ],
} satisfies components['schemas']['PasswordPolicyRead']
