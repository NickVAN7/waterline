import { describe, expect, it } from 'vitest'

import { readDraft } from './templates'

const DRAFT = { title: 'Refunds', description_md: 'Typed', priority: 'high', parent_id: '' }

describe('readDraft', () => {
  it('reads a draft from a history entry, leaving out anything else there', () => {
    expect(readDraft({ back: '/x', draft: { ...DRAFT, extra: 1 } })).toEqual(DRAFT)
  })

  it.each([
    ['no state', null],
    ['no draft', { back: '/x' }],
    ['a title not a string', { draft: { ...DRAFT, title: 1 } }],
    ['no description', { draft: { ...DRAFT, description_md: undefined } }],
    ['a parent not a string', { draft: { ...DRAFT, parent_id: null } }],
    ['an unknown priority', { draft: { ...DRAFT, priority: 'urgent' } }],
    ["a priority from the object's prototype", { draft: { ...DRAFT, priority: 'toString' } }],
  ])('is undefined for %s', (_, state) => {
    expect(readDraft(state)).toBeUndefined()
  })
})
