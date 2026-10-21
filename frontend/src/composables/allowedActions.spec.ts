import { describe, expect, it } from 'vitest'

import { allows } from './allowedActions'

describe('allows', () => {
  it('is true only for an action the entity lists', () => {
    const org = { allowed_actions: ['project.create' as const] }

    expect(allows(org, 'project.create')).toBe(true)
    expect(allows(org, 'project.assign_first_admin')).toBe(false)
  })

  it.each([null, undefined])('is false for a %s entity', (entity) => {
    expect(allows(entity, 'project.create')).toBe(false)
  })
})
