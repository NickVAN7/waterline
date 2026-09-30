import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'

import { client } from '@/api/client'
import App from '@/App.vue'

import { createAppRouter } from './router'

async function mountAt(path: string) {
  vi.spyOn(client, 'GET').mockReturnValue(new Promise(() => {}))
  const router = createAppRouter(createMemoryHistory())
  await router.push(path)
  const wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('routes', () => {
  it('shows the home page at /', async () => {
    const wrapper = await mountAt('/')

    expect(wrapper.get('h2').text()).toBe('System status')
    expect(wrapper.text()).not.toContain('Page not found')
  })

  it.each(['/no-such-page', '/a/nested/unknown/path'])(
    'shows the not-found page at %s',
    async (path) => {
      const wrapper = await mountAt(path)

      expect(wrapper.get('h1').text()).toBe('Page not found')
      expect(wrapper.get('main a').attributes('href')).toBe('/')
    },
  )
})

describe('layout', () => {
  it.each(['/', '/no-such-page'])('frames %s with the header and navigation', async (path) => {
    const wrapper = await mountAt(path)

    expect(wrapper.get('header a').text()).toBe('Waterline')
    expect(wrapper.get('nav[aria-label=Main]').text()).toContain('Home')
    expect(wrapper.find('main').exists()).toBe(true)
  })
})
