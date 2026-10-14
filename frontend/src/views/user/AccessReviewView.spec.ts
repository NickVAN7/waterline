import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok } from '@/test/api'
import { cleanUpAfterEach, mountWorkspaceView } from '@/test/workspace'

import AccessReviewView from './AccessReviewView.vue'

const REVIEW: components['schemas']['AccessReview'] = {
  user: {
    id: 'u-sam',
    email: 'sam@harbor.example',
    username: 'sam',
    name: 'Sam Member',
    is_active: false,
    is_system_admin: false,
    workspace_role: null,
  },
  orgs: [{ id: 'o-acme', name: 'Acme Manufacturing', slug: 'acme', reasons: ['org_member'] }],
  projects: [
    {
      id: 'p-erp',
      key: 'ERP',
      name: 'ERP rollout',
      organization_id: 'o-acme',
      archived: false,
      reasons: ['project_member'],
      access: 'content',
    },
  ],
}

beforeEach(() => setActivePinia(createPinia()))
cleanUpAfterEach()

describe('AccessReviewView', () => {
  it('lists every org and project the person reaches, and why', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(ok(REVIEW))

    const { wrapper } = await mountWorkspaceView(AccessReviewView, '/workspace/users/u-sam/access')

    expect(get).toHaveBeenCalledWith('/api/users/{user_id}/access', {
      params: { path: { user_id: 'u-sam' } },
    })
    expect(wrapper.get('h1').text()).toBe('Access review: Sam Member')
    expect(wrapper.text()).toContain('Deactivated')
    const rows = (heading: string) =>
      wrapper
        .findAll('table')
        .find(
          (t) => document.getElementById(t.attributes('aria-labelledby')!)?.textContent === heading,
        )!
        .findAll('tbody tr')
        .map((tr) => tr.findAll('td').map((td) => td.text()))
    expect(rows('Organizations')).toEqual([['Acme Manufacturing', 'Org member']])
    expect(rows('Projects')).toEqual([
      ['ERP ERP rollout', 'Acme Manufacturing', 'Project member', 'Content and management'],
    ])
    await expectNoA11yViolations(wrapper)
  })

  it('says so when they reach nothing', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(ok({ ...REVIEW, orgs: [], projects: [] }))

    const { wrapper } = await mountWorkspaceView(AccessReviewView, '/workspace/users/u-sam/access')

    expect(wrapper.text()).toContain("They can't reach any organization.")
    expect(wrapper.text()).toContain("They can't reach any project.")
  })

  it('is the not-found page on any denial (user.view_access is a 404)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      failed(404, { code: 'not_found', message: '', details: {} }),
    )

    const { wrapper } = await mountWorkspaceView(AccessReviewView, '/workspace/users/u-x/access')

    expect(wrapper.get('h1').text()).toBe('Page not found')
  })
})
