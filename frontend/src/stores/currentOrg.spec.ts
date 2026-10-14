import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import { ACME, me } from '@/test/api'
import { project } from '@/test/projects'

import { useCurrentOrgStore } from './currentOrg'
import { useCurrentUserStore } from './currentUser'

const GLOBEX = {
  ...ACME,
  id: '0190f0a0-0000-7000-8000-0000000000a2',
  name: 'Globex',
  slug: 'globex',
}

beforeEach(() => {
  setActivePinia(createPinia())
  useCurrentUserStore().me = me({ orgs: [ACME, GLOBEX] })
})

describe('the current org', () => {
  it("is the user's first org until a page says otherwise", () => {
    expect(useCurrentOrgStore().org?.slug).toBe('acme')
  })

  it('is the org a page entered, and stays after leaving it', () => {
    const nav = useCurrentOrgStore()

    nav.enter('globex')

    expect(nav.org?.slug).toBe('globex')
  })

  it('falls back to the first org for a slug the user does not have', () => {
    const nav = useCurrentOrgStore()

    nav.enter('initech')

    expect(nav.org?.slug).toBe('acme')
  })

  it('is none for a user with no orgs', () => {
    useCurrentUserStore().me = me({ orgs: [] })

    expect(useCurrentOrgStore().org).toBeNull()
  })
})

describe('the selected project', () => {
  it('becomes the selected project and makes its org current', () => {
    const nav = useCurrentOrgStore()

    nav.select(project({ organization_id: GLOBEX.id }))

    expect(nav.project?.key).toBe('ERP')
    expect(nav.org?.slug).toBe('globex')
  })

  it('is cleared on entering another org, and kept in its own', () => {
    const nav = useCurrentOrgStore()
    nav.select(project())

    nav.enter('acme')
    expect(nav.project?.key).toBe('ERP')

    nav.enter('globex')
    expect(nav.project).toBeNull()
  })

  it('is cleared, with the org, when someone else signs in', async () => {
    const nav = useCurrentOrgStore()
    nav.select(project({ organization_id: GLOBEX.id }))

    useCurrentUserStore().me = me({
      user: { id: 'another', email: 'max@harbor.example', username: 'max', name: 'Max' },
      orgs: [ACME, GLOBEX],
    })
    await nextTick()

    expect(nav.project).toBeNull()
    expect(nav.org?.slug).toBe('acme')
  })
})
