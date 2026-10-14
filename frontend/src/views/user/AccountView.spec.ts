import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { client } from '@/api/client'
import { useCurrentUserStore } from '@/stores/currentUser'
import { expectNoA11yViolations } from '@/test/a11y'
import { failed, me, ok, PASSWORD_POLICY, validationFailed } from '@/test/api'
import { testRouter } from '@/test/router'

import AccountView from './AccountView.vue'

async function mountView() {
  vi.spyOn(client, 'GET').mockResolvedValue(ok(PASSWORD_POLICY))
  useCurrentUserStore().me = me()
  const router = await testRouter('/account')
  const wrapper = mount(AccountView, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return wrapper
}

async function saveProfile(
  wrapper: Awaited<ReturnType<typeof mountView>>,
  name: string,
  username: string,
) {
  await wrapper.get('#name').setValue(name)
  await wrapper.get('#username').setValue(username)
  await wrapper.findAll('form')[0]!.trigger('submit')
  await flushPromises()
}

const saveButton = (wrapper: Awaited<ReturnType<typeof mountView>>) =>
  wrapper.findAll('button').find((b) => b.text() === 'Save profile')!

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('AccountView', () => {
  it('shows the profile, filled in, and the password form with its requirements', async () => {
    const wrapper = await mountView()

    expect(wrapper.get('h1').text()).toBe('Account settings')
    expect(wrapper.findAll('h2').map((h) => h.text())).toEqual(['Profile', 'Password'])
    expect((wrapper.get('#name').element as HTMLInputElement).value).toBe('Casey Cole')
    expect((wrapper.get('#username').element as HTMLInputElement).value).toBe('casey')
    expect(wrapper.text()).toContain('casey@harbor.example')
    expect(wrapper.find('#email').exists()).toBe(false)
    expect(wrapper.find('#new_password-requirements').exists()).toBe(true)
    expect(wrapper.findAll('button').map((b) => b.text())).not.toContain('Sign out')
    // One primary action on the page (UI-FRM-15): the password form's button is secondary.
    const change = wrapper.findAll('button').find((b) => b.text() === 'Change password')!
    expect(change.classes()).toContain('border-border')
    await expectNoA11yViolations(wrapper)
  })

  it('saves the profile and shows the new name to the rest of the app', async () => {
    const patch = vi
      .spyOn(client, 'PATCH')
      .mockResolvedValue(ok({ ...me().user, name: 'Casey Cole-Park', username: 'casey-park' }))
    const wrapper = await mountView()

    await saveProfile(wrapper, 'Casey Cole-Park', 'casey-park')

    expect(patch).toHaveBeenCalledWith('/api/me', {
      body: { name: 'Casey Cole-Park', username: 'casey-park' },
    })
    expect(useCurrentUserStore().me?.user).toMatchObject({
      name: 'Casey Cole-Park',
      username: 'casey-park',
    })
    // Seen, not only heard: there's no other sign the save worked.
    const saved = wrapper.findAll('[aria-live=polite]')[0]!
    expect(saved.text()).toBe('Profile saved.')
    expect(saved.classes()).not.toContain('sr-only')
    expect(saved.find('svg').exists()).toBe(true)

    // Edited again, it isn't saved any more.
    await wrapper.get('#name').setValue('Casey C.')
    expect(saved.text()).toBe('')
  })

  it("shows the server's message under a refused username and focuses it", async () => {
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      validationFailed([
        { loc: ['body', 'username'], message: 'That username is taken.', type: 'taken' },
      ]),
    )
    const wrapper = await mountView()

    await saveProfile(wrapper, 'Casey Cole', 'max')

    expect(wrapper.get('#username-error').text()).toBe('That username is taken.')
    expect(document.activeElement).toBe(wrapper.get('#username').element)
    expect(useCurrentUserStore().me?.user.username).toBe('casey')
  })

  it('sends nothing with an empty name, and focuses it', async () => {
    const patch = vi.spyOn(client, 'PATCH')
    const wrapper = await mountView()

    await saveProfile(wrapper, '', 'casey')

    expect(patch).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(wrapper.get('#name').element)
  })

  it('shows a failed save as an alert whose Retry saves again', async () => {
    const patch = vi
      .spyOn(client, 'PATCH')
      .mockResolvedValueOnce(failed(503, { code: 'network_error', message: '', details: {} }))
      .mockResolvedValueOnce(ok(me().user))
    const wrapper = await mountView()
    await saveProfile(wrapper, 'Casey Cole', 'casey')
    expect(wrapper.get('[role=alert]').text()).toContain("We couldn't reach the server.")

    await wrapper
      .findAll('button')
      .find((b) => b.text() === 'Retry')!
      .trigger('click')
    await flushPromises()

    expect(patch).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    // Retry moved focus to the control whose action failed (UI-FRM-7).
    expect(document.activeElement).toBe(saveButton(wrapper).element)
  })

  it('returns focus to Save profile when its failure alert is dismissed, and says so', async () => {
    vi.spyOn(client, 'PATCH').mockResolvedValue(
      failed(503, { code: 'network_error', message: '', details: {} }),
    )
    const wrapper = await mountView()
    await saveProfile(wrapper, 'Casey Cole', 'casey')

    await wrapper.get('button[aria-label="Dismiss alert"]').trigger('click')

    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    expect(document.activeElement).toBe(saveButton(wrapper).element)
    await vi.waitFor(() =>
      expect(wrapper.findAll('.sr-only[aria-live=polite]')[0]!.text()).toBe('Alert dismissed'),
    )
  })
})
