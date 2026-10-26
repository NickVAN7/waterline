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
      export_controlled: false,
      reasons: ['project_member'],
      access: 'content',
    },
  ],
}
const EXPORT_CONTROLLED = {
  ...REVIEW.projects[0]!,
  id: 'p-sec',
  key: 'SEC',
  name: 'Secret',
  export_controlled: true,
  reasons: ['org_admin' as const],
  access: 'management' as const,
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
    // No export-controlled project, so no Access column (DL-177).
    expect(rows('Projects')).toEqual([['ERP ERP rollout', 'Acme Manufacturing', 'Project member']])
    expect(wrapper.findAll('th').map((th) => th.text())).not.toContain('Access')
    await expectNoA11yViolations(wrapper)
  })

  it('shows Access, on the export-controlled projects only, when one is (DL-177)', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(
      ok({ ...REVIEW, projects: [...REVIEW.projects, EXPORT_CONTROLLED] }),
    )

    const { wrapper } = await mountWorkspaceView(AccessReviewView, '/workspace/users/u-sam/access')

    const projects = wrapper.findAll('table')[1]!
    expect(projects.findAll('th').map((th) => th.text())).toEqual([
      'Project',
      'Organization',
      'Why they reach it',
      'Access',
    ])
    expect(
      projects.findAll('tbody tr').map((tr) => tr.findAll('td').map((td) => td.text())),
    ).toEqual([
      // Blank to the eye, explained to a screen reader (DL-184).
      ['ERP ERP rollout', 'Acme Manufacturing', 'Project member', 'Not export-controlled'],
      ['SEC Secret', 'Acme Manufacturing', 'Org admin', 'Management only'],
    ])
    expect(projects.get('tbody td:last-child span').classes()).toContain('sr-only')
    await expectNoA11yViolations(wrapper)
  })

  it.each([
    [null, false, 'None'],
    ['owner', true, 'Owner, System admin'],
    [null, true, 'System admin'],
    ['member', false, 'Member'],
  ] as const)(
    'shows the workspace role %s with system admin %s as text: %s (DL-189)',
    async (role, isSystemAdmin, shown) => {
      const user = { ...REVIEW.user, workspace_role: role, is_system_admin: isSystemAdmin }
      vi.spyOn(client, 'GET').mockResolvedValue(ok({ ...REVIEW, user }))

      const { wrapper } = await mountWorkspaceView(
        AccessReviewView,
        '/workspace/users/u-sam/access',
      )

      const terms = wrapper.findAll('dt').map((dt) => dt.text())
      const details = wrapper.findAll('dd').map((dd) => dd.text())
      expect(details[terms.indexOf('Workspace role')]).toBe(shown)
      // System admin is no longer a badge beside the status.
      expect(details[terms.indexOf('Status')]).toBe('Deactivated')
    },
  )

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
