import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import { client, type ErrorBody } from '@/api/client'
import type { components } from '@/api/schema'

import HomeView from './HomeView.vue'

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

describe('HomeView', () => {
  it('shows that it is checking until the health check answers', () => {
    vi.spyOn(client, 'GET').mockReturnValue(new Promise(() => {}))

    const wrapper = mount(HomeView)

    expect(wrapper.get('[role=status]').text()).toBe('Checking…')
  })

  it('calls the health endpoint and shows that the system is up', async () => {
    const get = vi.spyOn(client, 'GET').mockResolvedValue(healthy())

    const wrapper = mount(HomeView)
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/health')
    expect(wrapper.get('[role=status]').text()).toBe('The API and database are up.')
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
  })

  it("shows the server's message when the database is down", async () => {
    vi.spyOn(client, 'GET').mockResolvedValue(unavailable())

    const wrapper = mount(HomeView)
    await flushPromises()

    expect(wrapper.get('[role=alert]').text()).toBe('The database is unavailable.')
    expect(wrapper.find('[role=status]').exists()).toBe(false)
  })

  it('leaves an unexpected error to the app instead of showing it as a status', async () => {
    const bug = new RangeError('bug')
    vi.spyOn(client, 'GET').mockRejectedValue(bug)
    const errors: unknown[] = []

    const wrapper = mount(HomeView, {
      global: { config: { errorHandler: (error: unknown) => errors.push(error) } },
    })
    await flushPromises()

    expect(errors).toEqual([bug])
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
  })

  it('shows a connection message when the API is unreachable, and checks again on request', async () => {
    const get = vi
      .spyOn(client, 'GET')
      .mockResolvedValueOnce(proxyWithApiDown())
      .mockResolvedValueOnce(healthy())
    const wrapper = mount(HomeView)
    await flushPromises()
    expect(wrapper.get('[role=alert]').text()).toBe(
      'Could not reach the server. Check your connection and try again.',
    )

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(get).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[role=status]').text()).toBe('The API and database are up.')
  })
})
