import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { ACME, me } from '@/test/api'
import { stubResizeObserver } from '@/test/overlay'
import { testRouter } from '@/test/router'

import OrgMenu from './OrgMenu.vue'

const org = (n: number) => ({ ...ACME, id: `org-${n}`, name: `Org ${n}`, slug: `org-${n}` })

async function mountMenu(orgs: (typeof ACME)[]) {
  useCurrentUserStore().me = me({ orgs })
  const router = await testRouter('/')
  return mount(OrgMenu, {
    // Real transitions: the overlay's show and hide events fire from them.
    global: { plugins: [router, PrimeVue], stubs: { transition: false } },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  stubResizeObserver()
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('OrgMenu', () => {
  it("shows a single org's name as plain text, not a control, with nothing to manage", async () => {
    const wrapper = await mountMenu([ACME])

    expect(wrapper.text()).toBe('Acme Manufacturing')
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('shows nothing for a user with no orgs', async () => {
    const wrapper = await mountMenu([])

    expect(wrapper.text()).toBe('')
  })

  it('opens a popover of links to each org, marking the current one', async () => {
    const wrapper = await mountMenu([org(1), org(2)])
    useCurrentOrgStore().enter('org-2')
    await flushPromises()
    const button = wrapper.get('button')
    expect(button.text()).toContain('Org 2')
    expect(button.attributes('aria-expanded')).toBe('false')

    await button.trigger('click')
    await flushPromises()

    await vi.waitFor(() => expect(button.attributes('aria-expanded')).toBe('true'))
    const dialog = document.querySelector('[role=dialog]')!
    expect(dialog.getAttribute('aria-label')).toBe('Organizations')
    const links = [...dialog.querySelectorAll('a')]
    expect(links.map((a) => [a.textContent?.trim(), a.getAttribute('href')])).toEqual([
      ['Org 1', '/org-1/projects'],
      ['Org 2', '/org-2/projects'],
    ])
    expect(links.map((a) => a.getAttribute('aria-current'))).toEqual([null, 'true'])
    // Focus moves inside, to the current org: the popover sits at the end of the body, out of
    // the Tab order after the button.
    expect(document.activeElement).toBe(links[1])
    expect(dialog.querySelector('input')).toBeNull()
    await expectNoA11yViolations(document.body)
  })

  it("adds the org's Overview, Members, and Settings for whoever may manage it, one org or more (UI-SHL-4, DL-163)", async () => {
    const wrapper = await mountMenu([{ ...ACME, allowed_actions: ['org_member.manage'] }])
    // The popover's portal mounts a tick later; a click before then skips its enter transition.
    await flushPromises()
    const button = wrapper.get('button')
    expect(button.text()).toContain('Acme Manufacturing')

    await button.trigger('click')
    await flushPromises()

    const links = [...document.querySelectorAll('[role=dialog] a')]
    expect(links.map((a) => [a.textContent?.trim(), a.getAttribute('href')])).toEqual([
      ['Acme Manufacturing', '/acme/projects'],
      ['Overview', '/acme/overview'],
      ['Members', '/acme/members'],
      ['Settings', '/acme/settings'],
    ])
    // Named for the org, so the links read as its own after the list of orgs.
    expect(
      document.querySelector('[role=dialog] ul[aria-label="Acme Manufacturing administration"]')
        ?.textContent,
    ).toMatch(/Overview\s*Members\s*Settings/)
    await expectNoA11yViolations(document.body)
  })

  it("offers no admin pages to someone who can't manage the org", async () => {
    const wrapper = await mountMenu([org(1), org(2)])
    await flushPromises()
    await wrapper.get('button').trigger('click')
    await flushPromises()

    const links = [...document.querySelectorAll('[role=dialog] a')]
    expect(links.map((a) => a.textContent?.trim())).toEqual(['Org 1', 'Org 2'])
  })

  it('adds a filter field past eight orgs', async () => {
    const wrapper = await mountMenu(Array.from({ length: 9 }, (_, i) => org(i + 1)))
    await wrapper.get('button').trigger('click')
    await flushPromises()
    const filter = document.querySelector<HTMLInputElement>('[role=dialog] input')!
    expect(document.activeElement).toBe(filter)
    expect(document.querySelector(`label[for="${filter.id}"]`)?.textContent).toBe(
      'Filter organizations',
    )

    filter.value = 'org 9'
    filter.dispatchEvent(new Event('input'))
    await flushPromises()

    const links = [...document.querySelectorAll('[role=dialog] a')]
    expect(links.map((a) => a.textContent?.trim())).toEqual(['Org 9'])
  })
})

// Registered after the clean-up above, so it runs first (after-hooks run last to first): each
// wrapper, and its overlay, is unmounted before the body is cleared.
enableAutoUnmount(afterEach)
