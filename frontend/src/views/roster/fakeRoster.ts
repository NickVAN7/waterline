/** A roster for the roster dialogs' specs: its endpoints are spies, answering success unless told. */
import { vi } from 'vitest'

import { ApiError } from '@/api/client'

import type { Roster, RosterPerson } from './roster'

export type Role = 'owner' | 'admin' | 'member'

export const PEOPLE: RosterPerson[] = [
  { user_id: 'u-olga', name: 'Olga Owner', email: 'olga@acme.example', is_active: true },
  { user_id: 'u-ada', name: 'Ada Admin', email: 'ada@acme.example', is_active: true },
  { user_id: 'u-dee', name: 'Dee Gone', email: 'dee@acme.example', is_active: false },
]

export function fakeRoster(): Roster & {
  add: ReturnType<typeof vi.fn>
  create: ReturnType<typeof vi.fn>
  changeRole: ReturnType<typeof vi.fn>
  remove: ReturnType<typeof vi.fn>
} {
  return {
    scope: "the workspace's staff",
    projects: "the workspace's projects",
    roles: [
      { value: 'owner', label: 'Owner' },
      { value: 'admin', label: 'Admin' },
      { value: 'member', label: 'Member' },
    ],
    workspaceId: 'ws',
    add: vi.fn().mockResolvedValue({}),
    create: vi.fn().mockResolvedValue({}),
    changeRole: vi.fn().mockResolvedValue({}),
    remove: vi.fn().mockResolvedValue(undefined),
    everyone: () => Promise.resolve(PEOPLE),
  }
}

/** The `ApiError` a roster call throws for a 422 with these field errors. */
export function invalid(...fields: { loc: string[]; message: string; type: string }[]) {
  return new ApiError(422, {
    code: 'validation_error',
    message: 'Check the highlighted fields.',
    details: { fields },
  })
}
