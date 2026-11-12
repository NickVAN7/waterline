import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { expectNoA11yViolations } from '@/test/a11y'

import DocsNav from './DocsNav.vue'

async function mountAt(path: string) {
  const Page = { template: '<p />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/docs', name: 'docs', component: Page },
      { path: '/docs/:slug', name: 'docs-page', component: Page },
    ],
  })
  await router.push(path)
  const wrapper = mount(DocsNav, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('DocsNav', () => {
  it('lists Documentation, then each group with its pages (DL-338)', async () => {
    const wrapper = await mountAt('/docs')

    const nav = wrapper.get('nav[aria-label="Documentation"]')
    expect(nav.get('a').text()).toBe('Documentation')
    const lists = nav.findAll('ul')
    expect(
      lists.map((ul) => document.getElementById(ul.attributes('aria-labelledby')!)?.textContent),
    ).toEqual(['Get started', 'Using Waterline', 'Administration', 'Reference'])
    expect(lists[2]!.findAll('a').map((a) => a.text())).toEqual([
      'Workspace',
      'Organizations',
      'System status',
    ])
  })

  it('marks the landing page on the landing page, and only it', async () => {
    const wrapper = await mountAt('/docs')

    expect(wrapper.findAll('[aria-current="page"]').map((a) => a.text())).toEqual(['Documentation'])
  })

  it('marks the page being read, a section hash included, and not the landing page', async () => {
    const wrapper = await mountAt('/docs/trash#restore-a-requirement')

    expect(wrapper.findAll('[aria-current="page"]').map((a) => a.text())).toEqual(['Trash'])
  })

  it('has no accessibility violations', async () => {
    const wrapper = await mountAt('/docs/trash')

    expect(wrapper.find('[aria-current="page"]').text()).toBe('Trash')
    await expectNoA11yViolations(wrapper)
  })
})
