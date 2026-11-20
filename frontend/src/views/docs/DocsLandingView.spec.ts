import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { expectNoA11yViolations } from '@/test/a11y'

import DocsLandingView from './DocsLandingView.vue'

async function mountLanding() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/docs', name: 'docs', component: DocsLandingView },
      { path: '/docs/:slug', name: 'docs-page', component: { template: '<p />' } },
    ],
  })
  await router.push('/docs')
  const wrapper = mount(DocsLandingView, {
    global: { plugins: [router] },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('DocsLandingView', () => {
  it('has the h1 Documentation and its one-line intro (DL-339)', async () => {
    const wrapper = await mountLanding()

    expect(wrapper.findAll('h1').map((h) => h.text())).toEqual(['Documentation'])
    expect(wrapper.text()).toContain(
      'How to plan, track, and sign off on your projects in Waterline.',
    )
  })

  it('starts with three Start here cards, each a link to its page with an icon', async () => {
    const wrapper = await mountLanding()

    const start = wrapper.get('section[aria-labelledby="docs-start"]')
    expect(start.get('h2').text()).toBe('Start here')
    const cards = start.findAll('a')
    expect(cards.map((a) => [a.find('.text-lg').text(), a.attributes('href')])).toEqual([
      ['Welcome to Waterline', '/docs/welcome'],
      ['Set up a project', '/docs/working-with-projects'],
      ['Review and approve', '/docs/approvals'],
    ])
    expect(cards.every((a) => a.find('svg').exists())).toBe(true)
  })

  it("lists each group's pages as cards, with each page's description", async () => {
    const wrapper = await mountLanding()

    const groups = wrapper.findAll('section').slice(1)
    expect(groups.map((g) => g.get('h2').text())).toEqual([
      'Get started',
      'Using Waterline',
      'Administration',
      'Reference',
    ])
    const trash = groups[1]!.get('a[href="/docs/trash"]')
    expect(trash.text()).toBe('TrashDelete a requirement, and bring a deleted one back.')
  })

  it('says who Administration is for, and shows it to everyone (DL-337)', async () => {
    const wrapper = await mountLanding()

    const admin = wrapper.findAll('section')[3]!
    expect(admin.text()).toContain('For workspace and organization owners and admins.')
    expect(admin.findAll('a').map((a) => a.attributes('href'))).toEqual([
      '/docs/workspace',
      '/docs/organizations',
      '/docs/system-status',
    ])
  })

  it('has no accessibility violations', async () => {
    const wrapper = await mountLanding()

    expect(wrapper.findAll('section')).toHaveLength(5)
    await expectNoA11yViolations(wrapper)
  })
})
