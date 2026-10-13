import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { installRouteFocus } from './routeFocus'

const First = { template: '<h1>My work</h1>' }
const Second = { template: '<h1>  Page not found </h1>' }
const NoHeading = { template: '<p>nothing</p>' }

async function setUp() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: First },
      { path: '/missing', component: Second },
      { path: '/bare', component: NoHeading },
    ],
  })
  installRouteFocus(router)
  // Mounted before the first navigation ends, as in the app (the guard waits for /me).
  mount(
    { template: '<main><RouterView /></main>' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await router.push('/')
  return router
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('route focus', () => {
  it('names the page after its h1, without moving focus on the first load', async () => {
    await setUp()
    await new Promise((resolve) => setTimeout(resolve))

    expect(document.title).toBe('My work · Waterline')
    expect(document.activeElement).toBe(document.body)
  })

  it('moves focus to the new h1 and renames the page on navigation', async () => {
    const router = await setUp()

    await router.push('/missing')
    await new Promise((resolve) => setTimeout(resolve))

    const heading = document.querySelector('h1')
    expect(document.activeElement).toBe(heading)
    expect(heading?.getAttribute('tabindex')).toBe('-1')
    expect(document.title).toBe('Page not found · Waterline')
  })

  it('falls back to the app name for a page with no h1', async () => {
    const router = await setUp()

    await router.push('/bare')
    await new Promise((resolve) => setTimeout(resolve))

    expect(document.title).toBe('Waterline')
  })
})
