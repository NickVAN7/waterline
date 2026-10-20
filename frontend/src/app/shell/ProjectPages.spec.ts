import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, ok } from '@/test/api'
import { project } from '@/test/projects'
import { testRouter } from '@/test/router'

import ProjectPages from './ProjectPages.vue'

type Action = components['schemas']['Action']

const guidance = (available: boolean) =>
  ok({
    modules: [
      { module: 'sprints', note: '', available },
      { module: 'github', note: '', available },
    ],
    types: [],
  })

async function mountWith(
  answer: unknown,
  enabled: ('sprints' | 'github')[] = ['sprints'],
  allowed: Action[] = [],
) {
  vi.spyOn(client, 'GET').mockResolvedValue(answer as never)
  const router = await testRouter('/')
  const wrapper = mount(ProjectPages, {
    props: {
      project: project({ enabled_modules: enabled, allowed_actions: allowed }),
      orgSlug: 'acme',
    },
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

describe('ProjectPages', () => {
  it("links Home, and shows an enabled module that hasn't shipped as text, not a link", async () => {
    const wrapper = await mountWith(guidance(false))

    expect(wrapper.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Home', '/acme/projects/ERP'],
    ])
    expect(wrapper.get('p').text().replace(/\s+/g, ' ')).toBe('Sprints Not available yet')
    await expectNoA11yViolations(wrapper)
  })

  it('shows only the modules the project enables', async () => {
    const wrapper = await mountWith(guidance(false), ['github'])

    expect(wrapper.findAll('p').map((p) => p.text().replace(/\s+/g, ' '))).toEqual([
      'GitHub Not available yet',
    ])
  })

  it('claims nothing about a module that is available, or when guidance fails', async () => {
    const available = await mountWith(guidance(true))
    expect(available.find('p').exists()).toBe(false)

    const unknown = await mountWith(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    expect(unknown.find('p').exists()).toBe(false)
  })

  it.each<Action>([
    'project.update',
    'project.raise_classification',
    'project.archive',
    'project.unarchive',
  ])('links Settings for whoever it offers anything: %s', async (action) => {
    const wrapper = await mountWith(guidance(true), [], [action])

    expect(wrapper.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Home', '/acme/projects/ERP'],
      ['Settings', '/acme/projects/ERP/settings'],
    ])
  })

  it('links no Settings with only project.view', async () => {
    const wrapper = await mountWith(guidance(true), [], ['project.view'])

    expect(wrapper.findAll('a').map((a) => a.text())).toEqual(['Home'])
  })
})
