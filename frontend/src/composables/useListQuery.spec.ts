import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useListQuery } from './useListQuery'

async function setUp(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/acme/projects', component: { template: '<p />' } }],
  })
  await router.push(path)
  let list!: ReturnType<typeof useListQuery>
  mount(
    {
      setup() {
        list = useListQuery({ limit: 25 })
        return () => null
      },
    },
    { global: { plugins: [router] } },
  )
  return { router, list }
}

describe('useListQuery', () => {
  it('reads the page from the URL', async () => {
    const { list } = await setUp('/acme/projects?offset=50')

    expect(list.params.value).toEqual({ limit: 25, offset: 50 })
  })

  it.each(['', '?offset=-25', '?offset=abc', '?offset=2.5'])(
    'starts at the first page for %s',
    async (query) => {
      const { list } = await setUp(`/acme/projects${query}`)

      expect(list.offset.value).toBe(0)
    },
  )

  it('links to another page, keeping the rest of the query', async () => {
    const { router, list } = await setUp('/acme/projects?view=all')

    await router.push(list.linkTo(25))

    expect(router.currentRoute.value.fullPath).toBe('/acme/projects?view=all&offset=25')
    expect(list.params.value).toEqual({ limit: 25, offset: 25 })
  })

  it('drops the offset for the first page', async () => {
    const { router, list } = await setUp('/acme/projects?offset=25')

    await router.push(list.linkTo(0))

    expect(router.currentRoute.value.fullPath).toBe('/acme/projects')
  })
})
