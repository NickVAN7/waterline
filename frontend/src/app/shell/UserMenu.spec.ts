import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { me } from '@/test/api'
import { stubResizeObserver } from '@/test/overlay'
import { testRouter } from '@/test/router'

import UserMenu from './UserMenu.vue'

async function openMenu() {
  useCurrentUserStore().me = me()
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
  localStorage.clear()
  delete document.documentElement.dataset.theme
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
    expect(items().map((li) => li.textContent?.trim())).toEqual([
      'Account settings',
      'System theme',
      'Light theme',
      'Dark theme',
      'Sign out',
    ])
    await expectNoA11yViolations(document.body)
  })

  it('offers the themes as radio items, System checked by default', async () => {
    await openMenu()

    const themes = items().filter((li) => li.getAttribute('role') === 'menuitemradio')
    expect(themes.map((li) => [li.textContent?.trim(), li.getAttribute('aria-checked')])).toEqual([
      ['System theme', 'true'],
      ['Light theme', 'false'],
      ['Dark theme', 'false'],
    ])
  })

  it('applies a chosen theme and checks it', async () => {
    const { wrapper } = await openMenu()

    await choose('Dark theme')

    expect(document.documentElement.dataset.theme).toBe('dark')
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(item('Dark theme').getAttribute('aria-checked')).toBe('true')
    expect(item('System theme').getAttribute('aria-checked')).toBe('false')
  })

  it('links to account settings', async () => {
    const { router } = await openMenu()
    const link = item('Account settings').querySelector('a')!
    expect(link.getAttribute('href')).toBe('/account')

    link.click()
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('account')
  })

  it('asks the shell to sign out', async () => {
    const { wrapper } = await openMenu()

    await choose('Sign out')

    expect(wrapper.emitted('signOut')).toHaveLength(1)
  })
})
