import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'

import { installRouteFocus } from '@/app/routeFocus'
import { expectNoA11yViolations } from '@/test/a11y'

import DocsView from './DocsView.vue'

// Another page, which focuses its own control once it settles (as a `settlesItself` page does).
const Other = {
  template: '<h1>Other</h1><button id="other">Other control</button>',
  mounted: () => document.getElementById('other')!.focus(),
}

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'my-work', component: Other, meta: { settlesItself: true } },
      { path: '/docs', name: 'docs', component: DocsView, meta: { settlesItself: true } },
    ],
  })
  installRouteFocus(router)
  await router.push(path)
  const wrapper = mount(
    { components: { RouterView }, template: '<main><RouterView /></main>' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await flushPromises()
  return { wrapper, router }
}

/** Run a navigation and let the page settle. */
async function settled(act: () => unknown) {
  await act()
  await flushPromises()
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('DocsView', () => {
  it("shows the user guide, its own heading the page's h1, and the window title from it (DL-310)", async () => {
    const { wrapper } = await mountAt('/docs')

    expect(wrapper.findAll('h1').map((h) => h.text())).toEqual(['User guide'])
    expect(wrapper.find('h2#docs-signing-in').text()).toBe('Signing in')
    expect(document.title).toBe('User guide · Waterline')
  })

  it("doesn't move focus on the first page load without a hash (UI-FRM-16)", async () => {
    await mountAt('/docs')

    expect(document.activeElement).toBe(document.body)
  })

  it('arriving from another page focuses the h1 (UI-SHL-9)', async () => {
    const { wrapper, router } = await mountAt('/')

    await settled(() => router.push('/docs'))

    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('lists the sections after the h1, each a link to its heading (DL-311)', async () => {
    const { wrapper } = await mountAt('/docs')

    const nav = wrapper.get('nav[aria-label="Contents"]')
    const links = nav.findAll('a')
    expect(links.slice(0, 2).map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Signing in', '/docs#docs-signing-in'],
      ['Getting around', '/docs#docs-getting-around'],
    ])
    expect(links.map((a) => a.text())).toContain('Documentation')
    // Title, then Contents, then the guide.
    const order = [...wrapper.element.querySelectorAll('h1, nav, h2')].map((el) => el.tagName)
    expect(order.slice(0, 3)).toEqual(['H1', 'NAV', 'H2'])
  })

  it("opened with a section's hash, focuses that section's heading (DL-311)", async () => {
    const { wrapper } = await mountAt('/docs#docs-account-settings')

    expect(document.activeElement).toBe(wrapper.get('#docs-account-settings').element)
  })

  it("leaves focus alone for a hash that isn't a guide section's", async () => {
    const { wrapper, router } = await mountAt('/')
    const app = document.createElement('div')
    app.id = 'app'
    document.body.append(app)

    await settled(() => router.push('/docs#app'))

    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('following a Contents link focuses its section, and Back the h1', async () => {
    const { wrapper, router } = await mountAt('/docs')
    await settled(() => wrapper.get('nav a[href="/docs#docs-my-work"]').trigger('click'))

    expect(document.activeElement).toBe(wrapper.get('#docs-my-work').element)

    await settled(() => router.back())

    expect(router.currentRoute.value.hash).toBe('')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('selecting the entry for the section already in the URL focuses it again (DL-311)', async () => {
    const { wrapper } = await mountAt('/docs#docs-my-work')
    const link = wrapper.get('nav a[href="/docs#docs-my-work"]')
    ;(link.element as HTMLElement).focus()

    await settled(() => link.trigger('click'))

    expect(document.activeElement).toBe(wrapper.get('#docs-my-work').element)
  })

  it("leaving /docs from a section leaves focus to the next page's own settling", async () => {
    const { router } = await mountAt('/docs#docs-my-work')

    await settled(() => router.push('/'))

    expect(document.activeElement?.id).toBe('other')
  })

  it('has no accessibility violations', async () => {
    const { wrapper } = await mountAt('/docs#docs-my-work')

    expect(document.activeElement?.id).toBe('docs-my-work')
    await expectNoA11yViolations(wrapper)
  })
})
