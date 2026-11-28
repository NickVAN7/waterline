import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { expectNoA11yViolations } from '@/test/a11y'
import { stubResizeObserver } from '@/test/overlay'
import { testRouter } from '@/test/router'

import Breadcrumbs, { type Crumb } from './Breadcrumbs.vue'

const ORG: Crumb = {
  label: 'Acme Manufacturing',
  icon: 'building',
  to: { name: 'org-projects', params: { orgSlug: 'acme' } },
}
const PROJECT: Crumb = {
  label: 'ERP Rollout',
  to: { name: 'project-home', params: { orgSlug: 'acme', key: 'ERP' } },
}
const REQUIREMENTS: Crumb = {
  label: 'Requirements',
  to: { name: 'project-requirements', params: { orgSlug: 'acme', key: 'ERP' } },
}
const PAGE: Crumb = { label: 'ERP-RQ-7', mono: true }

async function mountTrail(crumbs: Crumb[]) {
  const router = await testRouter('/acme/projects/ERP/requirements/7')
  const wrapper = mount(Breadcrumbs, {
    props: { crumbs },
    global: { plugins: [router, PrimeVue], stubs: { transition: false } },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, router }
}
// What a screen reader reaches: the list items PrimeVue's hidden separators leave out.
const crumbItems = () =>
  [...document.querySelectorAll<HTMLElement>('nav[aria-label=Breadcrumb] ol > li')].filter(
    (li) => !li.classList.contains('hidden'),
  )

beforeEach(stubResizeObserver)
afterEach(() => {
  document.body.innerHTML = ''
})
enableAutoUnmount(afterEach)

describe('Breadcrumbs', () => {
  it('is a named nav with an ordered list: each crumb a link but the last, the page (DL-327)', async () => {
    const { wrapper } = await mountTrail([ORG, PROJECT, PAGE])

    const nav = wrapper.get('nav')
    expect(nav.attributes('aria-label')).toBe('Breadcrumb')
    // The fold's "…" is there too: jsdom has no 40rem breakpoint to hide it.
    expect(crumbItems().map((li) => li.textContent!.trim())).toEqual([
      'Acme Manufacturing',
      '…',
      'ERP Rollout',
      'ERP-RQ-7',
    ])
    expect(nav.findAll('a').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Acme Manufacturing', '/acme/projects'],
      ['ERP Rollout', '/acme/projects/ERP'],
    ])
    const current = nav.get('[aria-current=page]')
    expect(current.text()).toBe('ERP-RQ-7')
    expect(current.element.tagName).toBe('SPAN')
    await expectNoA11yViolations(document.body)
  })

  it("shows an item's ID in mono, the org with its building icon, and decorative chevrons", async () => {
    const { wrapper } = await mountTrail([ORG, PROJECT, PAGE])

    expect(wrapper.get('[aria-current=page]').classes()).toContain('font-mono')
    expect(wrapper.get('a').findAll('svg')).toHaveLength(1)
    expect(wrapper.findAll('a')[1]!.findAll('svg')).toHaveLength(0)
    // One chevron before each crumb but the first, hidden from screen readers.
    const chevron = 'svg[aria-hidden=true]:has(path[d="M9 6l6 6-6 6"])'
    expect(crumbItems().map((li) => li.querySelectorAll(chevron).length)).toEqual([0, 1, 1, 1])
  })

  it("never marks a crumb that links to the page it's on as the page: only the last is", async () => {
    const here: Crumb = {
      label: 'Requirements',
      to: { name: 'project-requirement', params: { orgSlug: 'acme', key: 'ERP', number: '7' } },
    }
    const { wrapper } = await mountTrail([here, PAGE])

    expect(wrapper.findAll('[aria-current=page]').map((el) => el.text())).toEqual(['ERP-RQ-7'])
  })

  it('renders nothing with fewer than two crumbs: a top-level page has none', async () => {
    const { wrapper } = await mountTrail([PAGE])

    expect(wrapper.find('nav').exists()).toBe(false)
  })

  it('folds the middle crumbs under 40rem into a "…" menu button, keeping the first and last', async () => {
    const { wrapper } = await mountTrail([ORG, PROJECT, REQUIREMENTS, PAGE])

    const [first, fold, ...rest] = crumbItems()
    expect(first!.classList.contains('max-sm:hidden')).toBe(false)
    expect(fold!.classList).toContain('sm:hidden')
    expect(rest.map((li) => li.classList.contains('max-sm:hidden'))).toEqual([true, true, false])
    const button = wrapper.get('button')
    expect(button.attributes('aria-label')).toBe('Show 2 more levels')
    expect(button.attributes('aria-haspopup')).toBe('menu')
  })

  it('says one more level for a single folded crumb, and has no fold for two crumbs', async () => {
    const { wrapper } = await mountTrail([ORG, PROJECT, PAGE])
    expect(wrapper.get('button').attributes('aria-label')).toBe('Show 1 more level')

    await wrapper.setProps({ crumbs: [PROJECT, PAGE] })
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it("opens the fold's menu listing the folded crumbs as links, and following one navigates", async () => {
    const { wrapper, router } = await mountTrail([ORG, PROJECT, REQUIREMENTS, PAGE])
    const button = wrapper.get('button')

    await button.trigger('click')
    await flushPromises()

    expect(button.attributes('aria-expanded')).toBe('true')
    const menu = document.querySelector<HTMLElement>('[role=menu]')!
    expect(menu.getAttribute('aria-label')).toBe('Show 2 more levels')
    const links = [...menu.querySelectorAll<HTMLAnchorElement>('[role=menuitem] a')]
    expect(links.map((a) => [a.textContent!.trim(), a.getAttribute('href')])).toEqual([
      ['ERP Rollout', '/acme/projects/ERP'],
      ['Requirements', '/acme/projects/ERP/requirements'],
    ])
    await expectNoA11yViolations(document.body)

    links[1]!.click()
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements')
  })

  it.each(['ctrlKey', 'metaKey', 'shiftKey'])(
    'leaves a %s click on a folded crumb to the browser, for a new tab or window',
    async (key) => {
      const { wrapper, router } = await mountTrail([ORG, PROJECT, REQUIREMENTS, PAGE])
      await wrapper.get('button').trigger('click')
      await flushPromises()
      const link = document.querySelectorAll<HTMLAnchorElement>('[role=menuitem] a')[1]!
      // jsdom doesn't navigate on an anchor, so the default stands in for the new tab.
      link.addEventListener('click', (event) => event.preventDefault(), { once: true })
      const click = new MouseEvent('click', { bubbles: true, cancelable: true, [key]: true })
      const kept = vi.spyOn(click, 'preventDefault')

      link.dispatchEvent(click)
      await flushPromises()

      // Only the stand-in listener cancelled it; the menu didn't, nor did it navigate in the app.
      expect(kept).toHaveBeenCalledOnce()
      expect(router.currentRoute.value.fullPath).toBe('/acme/projects/ERP/requirements/7')
    },
  )
})
