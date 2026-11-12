import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useCurrentUserStore } from '@/stores/currentUser'
import { me } from '@/test/api'
import { project } from '@/test/projects'

import { projectCrumbs } from './crumbs'

beforeEach(() => setActivePinia(createPinia()))

describe('projectCrumbs', () => {
  it("starts at the project's org, then the project, then the page's own crumbs (DL-327)", () => {
    useCurrentUserStore().me = me()

    expect(projectCrumbs(project(), [{ label: 'Trash' }]).map((c) => c.label)).toEqual([
      'Acme Manufacturing',
      'ERP rollout',
      'Trash',
    ])
  })

  it("leaves the org out when the user's list doesn't hold it, keeping the project", () => {
    useCurrentUserStore().me = me({ orgs: [] })

    expect(projectCrumbs(project()).map((c) => c.label)).toEqual(['ERP rollout'])
  })
})
