import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { nextTick, shallowRef } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useListQuery } from './useListQuery'

async function setUp(path: string, offsetKey?: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/acme/projects', component: { template: '<p />' } }],
  })
  await router.push(path)
  let list!: ReturnType<typeof useListQuery<'status' | 'type'>>
  mount(
    {
      setup() {
        list = useListQuery({ limit: 25, filters: ['status', 'type'], offsetKey })
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

  it('sends the filters set in the URL, and only those', async () => {
    const { list } = await setUp('/acme/projects?status=active&type=&view=all&offset=25')

    expect(list.params.value).toEqual({ limit: 25, offset: 25, status: 'active' })
    expect(list.filter.value).toEqual({ status: 'active', type: '' })
    expect(list.filtering.value).toBe(true)
  })

  it('is not filtering with no filter set', async () => {
    const { list } = await setUp('/acme/projects?view=all')

    expect(list.filtering.value).toBe(false)
  })

  it('changes a filter from the first page, keeping the rest, and clears one with an empty value', async () => {
    const { router, list } = await setUp('/acme/projects?status=active&view=all&offset=50')

    await router.push(list.filtered({ type: 'erp' }))
    expect(router.currentRoute.value.fullPath).toBe(
      '/acme/projects?status=active&view=all&type=erp',
    )

    await router.push(list.filtered({ status: '', type: '' }))
    expect(router.currentRoute.value.fullPath).toBe('/acme/projects?view=all')
  })

  it('reads and links its page under its own name, leaving the other list alone', async () => {
    const { list } = await setUp('/acme/projects?offset=25&archived_offset=50', 'archived_offset')

    expect(list.params.value).toEqual({ limit: 25, offset: 50 })
    expect(list.linkTo(75)).toEqual({ query: { offset: '25', archived_offset: '75' } })
  })

  it('goes back to the first page when a later one loads empty (TD-58)', async () => {
    const { router, list } = await setUp('/acme/projects?offset=50&status=active')
    const page = shallowRef<{ items: string[] }>()
    list.returnWhenEmpty(page)

    page.value = { items: [] }
    await nextTick()
    await flushRouter(router)

    expect(router.currentRoute.value.fullPath).toBe('/acme/projects?status=active')
  })

  it.each([
    ['a page with rows', '/acme/projects?offset=50', ['PMT']],
    ['the first page, empty', '/acme/projects', []],
  ])('stays on %s', async (_, path, items) => {
    const { router, list } = await setUp(path)
    const page = shallowRef<{ items: string[] }>()
    list.returnWhenEmpty(page)

    page.value = { items }
    await nextTick()
    await flushRouter(router)

    expect(router.currentRoute.value.fullPath).toBe(path)
  })
})

/** Let a navigation started by the composable finish. */
async function flushRouter(router: ReturnType<typeof createRouter>) {
  await router.isReady()
  await new Promise((resolve) => setTimeout(resolve))
}
