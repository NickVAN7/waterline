import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'

import { installRouteFocus } from '@/app/routeFocus'
import { expectNoA11yViolations } from '@/test/a11y'

import DocsArticleView from './DocsArticleView.vue'

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
      { path: '/docs', name: 'docs', component: Other, meta: { settlesItself: true } },
      {
        path: '/docs/:slug',
        name: 'docs-page',
        component: DocsArticleView,
        meta: { settlesItself: true },
      },
      { path: '/status', name: 'status', component: Other },
    ],
  })
  installRouteFocus(router)
  await router.push(path)
  // Keyed on the path, as App.vue does: another page is a new mount.
  const wrapper = mount(
    { components: { RouterView }, template: '<main><RouterView :key="$route.path" /></main>' },
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

/** Put each named section's heading at a distance from the top of the window. */
function placeHeadings(tops: Record<string, number>) {
  for (const [id, top] of Object.entries(tops)) {
    vi.spyOn(document.getElementById(id)!, 'getBoundingClientRect').mockReturnValue({
      top,
    } as DOMRect)
  }
}

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('DocsArticleView', () => {
  it('shows the trail, the group above the h1, the lead, and the window title (DL-340)', async () => {
    const { wrapper } = await mountAt('/docs/trash')

    const trail = wrapper.get('nav[aria-label="Breadcrumb"]')
    expect(trail.get('a').text()).toBe('Documentation')
    expect(trail.get('[aria-current="page"]').text()).toBe('Trash')
    const order = [...wrapper.element.querySelectorAll('article > div:first-child > *')].map((el) =>
      el.textContent?.trim(),
    )
    expect(order.slice(1)).toEqual([
      'Using Waterline',
      'Trash',
      'Delete a requirement, and bring a deleted one back.',
    ])
    expect(wrapper.findAll('h1').map((h) => h.text())).toEqual(['Trash'])
    expect(document.title).toBe('Trash · Waterline')
  })

  it('renders the page in docs mode: its sections, callouts, and tables', async () => {
    const { wrapper } = await mountAt('/docs/trash')

    expect(wrapper.findAll('article h2').map((h) => h.attributes('id'))).toEqual([
      'delete-a-requirement',
      'restore-a-requirement',
    ])
    expect(wrapper.get('.callout strong').text()).toBe('Note')
    expect(wrapper.find('article table').exists()).toBe(true)
  })

  it('shows the not-found page for a page that does not exist', async () => {
    const { wrapper } = await mountAt('/docs/nothing')

    expect(wrapper.get('h1').text()).toBe('Page not found')
    expect(document.title).toBe('Page not found · Waterline')
  })

  it.each([
    ['/docs/welcome', undefined, 'My work'],
    ['/docs/trash', 'Members and roles', 'Your account'],
    ['/docs/keyboard-and-accessibility', 'System status', undefined],
  ])('%s links to the pages before and after it in nav order', async (path, previous, next) => {
    const { wrapper } = await mountAt(path)

    const nav = wrapper.get('nav[aria-label="Previous and next pages"]')
    const link = (word: string) =>
      nav
        .findAll('a')
        .find((a) => a.text().startsWith(word))
        ?.text()
        .slice(word.length)
    expect(link('Previous')).toBe(previous)
    expect(link('Next')).toBe(next)
  })

  it('Next opens the next page and focuses its h1 (UI-SHL-9)', async () => {
    const { wrapper, router } = await mountAt('/docs/trash')

    const next = wrapper.get('nav[aria-label="Previous and next pages"] a[href="/docs/account"]')
    await settled(() => next.trigger('click'))
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/docs/account'))
    await flushPromises()

    expect(document.activeElement).toBe(wrapper.get('h1').element)
    expect(wrapper.get('h1').text()).toBe('Your account')
  })

  it("lists On this page, the page's ## sections, each a link to its heading", async () => {
    const { wrapper } = await mountAt('/docs/trash')

    const nav = wrapper.get('nav[aria-label="On this page"]')
    expect(nav.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Delete a requirement', '/docs/trash#delete-a-requirement'],
      ['Restore a requirement', '/docs/trash#restore-a-requirement'],
    ])
  })

  it('marks the section being read, and follows the scroll (DL-340)', async () => {
    const { wrapper } = await mountAt('/docs/requirements')
    const current = () =>
      wrapper
        .findAll('nav[aria-label="On this page"] a[aria-current="location"]')
        .map((a) => a.text())

    const below = {
      'arrange-the-tree': 3000,
      'edit-a-requirement': 4000,
      'follow-its-history': 5000,
    }
    placeHeadings({ 'create-a-requirement': 900, 'open-a-requirement': 1800, ...below })
    window.dispatchEvent(new Event('scroll'))
    await flushPromises()
    // Nothing past the top third yet: the first section.
    expect(current()).toEqual(['Create a requirement'])

    // A heading exactly on the line, a third of the window down, counts as reached.
    const line = window.innerHeight / 3
    placeHeadings({ 'create-a-requirement': -400, 'open-a-requirement': line, ...below })
    window.dispatchEvent(new Event('scroll'))
    await flushPromises()
    expect(current()).toEqual(['Open a requirement'])
  })

  it("doesn't move focus on the first page load without a hash (UI-FRM-16)", async () => {
    await mountAt('/docs/trash')

    expect(document.activeElement).toBe(document.body)
  })

  it('arriving from another page focuses the h1 (UI-SHL-9)', async () => {
    const { wrapper, router } = await mountAt('/')

    await settled(() => router.push('/docs/trash'))

    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it("opened with a section's hash, focuses that section's heading (DL-338)", async () => {
    const { wrapper } = await mountAt('/docs/trash#restore-a-requirement')

    expect(document.activeElement).toBe(wrapper.get('#restore-a-requirement').element)
  })

  it("leaves focus alone for a hash that isn't one of the page's sections", async () => {
    const { wrapper, router } = await mountAt('/')
    const main = document.createElement('div')
    main.id = 'app'
    document.body.append(main)

    await settled(() => router.push('/docs/trash#app'))

    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('following an On this page link focuses its section, and Back the h1', async () => {
    const { wrapper, router } = await mountAt('/docs/trash')
    await settled(() =>
      wrapper.get('nav a[href="/docs/trash#restore-a-requirement"]').trigger('click'),
    )

    expect(document.activeElement).toBe(wrapper.get('#restore-a-requirement').element)

    await settled(() => router.back())

    expect(router.currentRoute.value.hash).toBe('')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
  })

  it('selecting the entry for the section already in the URL focuses it again', async () => {
    const { wrapper } = await mountAt('/docs/trash#restore-a-requirement')
    const link = wrapper.get('nav a[href="/docs/trash#restore-a-requirement"]')
    ;(link.element as HTMLElement).focus()

    await settled(() => link.trigger('click'))

    expect(document.activeElement).toBe(wrapper.get('#restore-a-requirement').element)
  })

  it('a link in the text to another guide page opens it in the app', async () => {
    const { wrapper, router } = await mountAt('/docs/requirements')

    const link = wrapper.get('article .markdown a[href="/docs/trash"]')
    await settled(() => link.trigger('click', { button: 0 }))

    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/docs/trash'))
  })

  it('a modified click on such a link is left to the browser (a new tab)', async () => {
    const { wrapper, router } = await mountAt('/docs/requirements')

    const link = wrapper.get('article .markdown a[href="/docs/trash"]')
    const click = new MouseEvent('click', {
      button: 0,
      ctrlKey: true,
      cancelable: true,
      bubbles: true,
    })
    link.element.dispatchEvent(click)
    await flushPromises()

    expect(click.defaultPrevented).toBe(false)
    expect(router.currentRoute.value.path).toBe('/docs/requirements')
  })

  it('a middle click on such a link is left to the browser', async () => {
    const { wrapper, router } = await mountAt('/docs/requirements')

    const link = wrapper.get('article .markdown a[href="/docs/trash"]')
    const click = new MouseEvent('click', { button: 1, cancelable: true, bubbles: true })
    link.element.dispatchEvent(click)
    await flushPromises()

    expect(click.defaultPrevented).toBe(false)
    expect(router.currentRoute.value.path).toBe('/docs/requirements')
  })

  it("leaving a page from a section leaves focus to the next page's own settling", async () => {
    const { router } = await mountAt('/docs/trash#restore-a-requirement')

    await settled(() => router.push('/'))

    expect(document.activeElement?.id).toBe('other')
  })

  it('has no accessibility violations', async () => {
    const { wrapper } = await mountAt('/docs/requirements#edit-a-requirement')

    expect(document.activeElement?.id).toBe('edit-a-requirement')
    await expectNoA11yViolations(wrapper)
  })
})
