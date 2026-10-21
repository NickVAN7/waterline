import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { client, type ErrorBody } from '@/api/client'
import type { components } from '@/api/schema'
import { expectNoA11yViolations } from '@/test/a11y'

import StatusView from './StatusView.vue'

type HealthRead = components['schemas']['HealthRead']
type HealthResult = Awaited<ReturnType<typeof client.GET>>

function healthy(): HealthResult {
  const data: HealthRead = { status: 'ok', database: 'ok' }
  return { data, response: new Response(null, { status: 200 }) }
}

/** What the Vite proxy answers when the API container is down: an empty 502. */
function proxyWithApiDown(): HealthResult {
  // Cast: the generated types only know the API's own responses, and this one isn't.
  return {
    error: undefined,
    response: new Response(null, { status: 502 }),
  } as unknown as HealthResult
}

function unavailable(): HealthResult {
  const error: ErrorBody = {
    code: 'service_unavailable',
    message: 'The database is unavailable.',
    details: { database: 'unavailable' },
  }
  return { error, response: new Response(null, { status: 503 }) }
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('StatusView', () => {
  it('shows that it is checking until the health check answers', () => {
    vi.spyOn(client, 'GET').mockReturnValue(new Promise(() => {}))

    const wrapper = mount(StatusView)

    expect(wrapper.get('h1').text()).toBe('System status')
    expect(wrapper.get('[role=status]').text()).toBe('Checking…')
  })

  it('calls the health endpoint and shows that the system is up', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(healthy())

    const wrapper = mount(StatusView, { attachTo: document.body })
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/health')
    expect(wrapper.get('[role=status]').text()).toBe('The API and database are up.')
    await expectNoA11yViolations(wrapper)
  })

  it("shows the server's message when the database is down, without announcing it on load", async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(unavailable())

    const wrapper = mount(StatusView, { attachTo: document.body })
    await flushPromises()

    expect(wrapper.text()).toContain('The database is unavailable.')
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    expect(wrapper.find('[role=status]').exists()).toBe(false)
    await expectNoA11yViolations(wrapper)
  })

  it('makes no old message an alert while checking again', async () => {
    let answer: (value: HealthResult) => void = () => {}
    vi.spyOn(client, 'GET')
      .mockResolvedValueOnce(proxyWithApiDown())
      .mockReturnValueOnce(new Promise<HealthResult>((resolve) => (answer = resolve)))
    const wrapper = mount(StatusView)
    await flushPromises()

    await wrapper.get('button').trigger('click')
    expect(wrapper.find('[role=alert]').exists()).toBe(false)

    answer(proxyWithApiDown())
    await flushPromises()
    expect(wrapper.find('[role=alert]').exists()).toBe(true)
  })

  it('says the server is not working, in our words, for an answer it cannot read', async () => {
    vi.spyOn(client, 'GET').mockResolvedValue({
      error: undefined,
      response: new Response('oops', { status: 500 }),
    } as unknown as HealthResult)
    const wrapper = mount(StatusView)
    await flushPromises()

    expect(wrapper.text()).toContain(
      "The server isn't working right now. Try again in a few minutes.",
    )
    expect(wrapper.text()).not.toContain('500')
  })

  it('leaves an unexpected error to the app instead of showing it as a status', async () => {
    const bug = new RangeError('bug')
    vi.spyOn(client, 'GET').mockRejectedValue(bug)
    const errors: unknown[] = []

    const wrapper = mount(StatusView, {
      global: { config: { errorHandler: (error: unknown) => errors.push(error) } },
    })
    await flushPromises()

    expect(errors).toEqual([bug])
    expect(wrapper.text()).not.toContain('bug')
  })

  it('shows a connection message when the API is unreachable, and checks again on request', async () => {
    const get = vi
      .spyOn(client, 'GET')
      .mockResolvedValueOnce(proxyWithApiDown())
      .mockResolvedValueOnce(proxyWithApiDown())
      .mockResolvedValueOnce(proxyWithApiDown())
      .mockResolvedValueOnce(healthy())
    const wrapper = mount(StatusView, { attachTo: document.body })
    await flushPromises()
    expect(wrapper.text()).toContain(
      'Could not reach the server. Check your connection and try again.',
    )

    // A check the user asked for that fails again is announced, and focus stays on the button.
    const button = wrapper.get('button').element
    button.focus()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role=alert]').text()).toContain('Could not reach the server.')
    expect(document.activeElement).toBe(button)
    const firstAlert = wrapper.get('[role=alert]').element

    // Failing again inserts a new alert, so the same text is announced again.
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role=alert]').element).not.toBe(firstAlert)

    // On success the button goes, so focus moves to the heading.
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(4)
    expect(wrapper.get('[role=status]').text()).toBe('The API and database are up.')
    expect(document.activeElement).toBe(wrapper.get('h1').element)
    wrapper.unmount()
  })
})
