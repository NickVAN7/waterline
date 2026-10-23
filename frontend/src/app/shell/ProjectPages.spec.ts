import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { project } from '@/test/projects'
import { testRouter } from '@/test/router'

import ProjectPages from './ProjectPages.vue'

type Action = components['schemas']['Action']

async function mountWith(allowed: Action[] = ['project.view']) {
  const router = await testRouter('/')
  const wrapper = mount(ProjectPages, {
    props: { project: project({ allowed_actions: allowed }), orgSlug: 'acme' },
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

describe('ProjectPages', () => {
  it('links Home and Members', async () => {
    const wrapper = await mountWith()

    expect(wrapper.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Home', '/acme/projects/ERP'],
      ['Members', '/acme/projects/ERP/members'],
    ])
    await expectNoA11yViolations(wrapper)
  })

  it.each<Action>([
    'project.update',
    'project.raise_restriction',
    'project.archive',
    'project.unarchive',
  ])('links Settings for whoever it offers anything: %s', async (action) => {
    const wrapper = await mountWith(['project.view', action])

    expect(wrapper.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Home', '/acme/projects/ERP'],
      ['Members', '/acme/projects/ERP/members'],
      ['Settings', '/acme/projects/ERP/settings'],
    ])
  })

  it('links no Members without project.view', async () => {
    const wrapper = await mountWith([])

    expect(wrapper.findAll('a').map((a) => a.text())).toEqual(['Home'])
  })

  it('links no Settings with only project.view', async () => {
    const wrapper = await mountWith(['project.view'])

    expect(wrapper.findAll('a').map((a) => a.text())).toEqual(['Home', 'Members'])
  })
})
