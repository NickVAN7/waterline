import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { ACME, me, workspaceEntry } from '@/test/api'
import { stubResizeObserver } from '@/test/overlay'
import { testRouter } from '@/test/router'

import UserMenu from './UserMenu.vue'

async function openMenu(overrides: Parameters<typeof me>[0] = {}) {
  useCurrentUserStore().me = me(overrides)
  const router = await testRouter('/')
  const wrapper = mount(UserMenu, {
    // Real transitions: the overlay's show and hide events fire from them.
    global: { plugins: [router, PrimeVue], stubs: { transition: false } },
    attachTo: document.body,
  })
  // The menu's portal mounts a tick later; a click before then skips its enter transition.
  await flushPromises()
  await wrapper.get('button').trigger('click')
  await flushPromises()
  return { wrapper, router }
}

const items = () => [...document.querySelectorAll<HTMLElement>('#user-menu [role^=menuitem]')]
const item = (label: string) => items().find((li) => li.textContent?.trim() === label)!

/** A menu item's action runs on its content's click, as PrimeVue's own click handler expects. */
async function choose(label: string) {
  item(label).querySelector<HTMLElement>('[data-pc-section=itemcontent]')!.click()
  await flushPromises()
}

beforeEach(() => {
  setActivePinia(createPinia())
  stubResizeObserver()
})

afterEach(() => {
  document.body.innerHTML = ''
})

// Registered after the clean-up above, so it runs first (after-hooks run last to first): each
// wrapper, and its overlay, is unmounted before the body is cleared.
enableAutoUnmount(afterEach)

describe('UserMenu', () => {
  it("is a menu button with the user's name that opens their menu", async () => {
    const { wrapper } = await openMenu()

    const button = wrapper.get('button')
    expect(button.text()).toContain('Casey Cole')
    expect(button.attributes('aria-haspopup')).toBe('menu')
    expect(button.attributes('aria-expanded')).toBe('true')
    expect(document.querySelector('#user-menu [role=menu]')?.getAttribute('aria-label')).toBe(
      'Account menu',
    )
    expect(items().map((li) => li.textContent?.trim())).toEqual(['Account settings', 'Sign out'])
    await expectNoA11yViolations(document.body)
  })

  it('links to account settings', async () => {
    const { router } = await openMenu()
    const link = item('Account settings').querySelector('a')!
    expect(link.getAttribute('href')).toBe('/account')

    link.click()
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('account')
  })

  it('links to the workspace pages, as Administration, for those who may see them (UI-SHL-10, DL-137)', async () => {
    const { router } = await openMenu({ workspaces: [workspaceEntry(['workspace.view'])] })
    const link = item('Administration').querySelector('a')!
    expect(link.getAttribute('href')).toBe('/workspace/staff')

    link.click()
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('workspace-staff')
  })

  it("has no Administration for staff who can't see the workspace pages", async () => {
    await openMenu({ workspaces: [workspaceEntry([])] })

    expect(items().map((li) => li.textContent?.trim())).not.toContain('Administration')
  })

  it("leaves an org's administration to the org menu (UI-SHL-4, DL-137)", async () => {
    await openMenu({
      orgs: [{ ...ACME, allowed_actions: ['org_member.manage'] }],
      workspaces: [workspaceEntry(['workspace.view'])],
    })
    useCurrentOrgStore().enter('acme')
    await flushPromises()

    expect(items().map((li) => li.textContent?.trim())).toEqual([
      'Account settings',
      'Administration',
      'Sign out',
    ])
  })

  it('sets Sign out apart with an icon and the danger tone (UI-SHL-4, DL-137)', async () => {
    await openMenu()

    const label = item('Sign out').querySelector('.text-danger')!
    expect(label.textContent?.trim()).toBe('Sign out')
    expect(label.querySelector('svg')).not.toBeNull()
    expect(item('Account settings').querySelector('.text-danger')).toBeNull()
  })

  it('asks the shell to sign out', async () => {
    const { wrapper } = await openMenu()

    await choose('Sign out')

    expect(wrapper.emitted('signOut')).toHaveLength(1)
  })
})
