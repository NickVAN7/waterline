import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { installRouteFocus, redirectInPlace, settlePage } from './routeFocus'

const First = { template: '<h1>My work</h1>' }
const Second = { template: '<h1>  Page not found </h1>' }
const NoHeading = { template: '<p>nothing</p>' }
const Loading = { template: '<h1>Loading heading</h1>' }

async function setUp(first = '/') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: First },
      { path: '/missing', component: Second },
      { path: '/bare', component: NoHeading },
      { path: '/later', component: Loading, meta: { settlesItself: true } },
      { path: '/later-fixed', component: Loading, meta: { settlesItself: true } },
    ],
  })
  installRouteFocus(router)
  // Mounted before the first navigation ends, as in the app (the guard waits for /me).
  mount(
    { template: '<main><RouterView /></main>' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await router.push(first)
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

  it('leaves focus and the title alone when only the query changes (TD-36)', async () => {
    const router = await setUp()
    await router.push('/missing')
    await new Promise((resolve) => setTimeout(resolve))
    const button = document.body.appendChild(document.createElement('button'))
    button.focus()

    await router.push('/missing?offset=25')
    await new Promise((resolve) => setTimeout(resolve))

    expect(document.activeElement).toBe(button)
    expect(document.title).toBe('Page not found · Waterline')
  })

  it('lets a page that loads its h1 settle itself, then names and focuses it', async () => {
    const router = await setUp()
    document.title = 'before'

    await router.push('/later')
    await new Promise((resolve) => setTimeout(resolve))
    expect(document.title).toBe('before')
    expect(document.activeElement).toBe(document.body)

    await settlePage()
    expect(document.title).toBe('Loading heading · Waterline')
    expect(document.activeElement).toBe(document.querySelector('h1'))
  })

  it('keeps the first page unfocused through a redirect to its own URL', async () => {
    const router = await setUp('/later')

    await redirectInPlace(() => router.replace('/later-fixed'))
    await settlePage()

    expect(document.activeElement).toBe(document.body)
    expect(document.title).toBe('Loading heading · Waterline')
  })

  it('still focuses a later page of the same kind', async () => {
    const router = await setUp('/later')
    await settlePage()

    await router.push('/later-fixed')
    await settlePage()

    expect(document.activeElement).toBe(document.querySelector('h1'))
  })
})
