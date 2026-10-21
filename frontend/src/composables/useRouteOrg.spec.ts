import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { defineComponent, h, nextTick, watchEffect } from 'vue'

import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import { ACME, me } from '@/test/api'
import { testRouter } from '@/test/router'

import { useRouteOrg } from './useRouteOrg'

const GLOBEX = { ...ACME, id: 'org-globex', name: 'Globex Retail', slug: 'globex' }

/** A page that shows its org's name, recording every value it took. */
async function mountAt(path: string) {
  // Copies: a test may edit an entry, as a slug change does.
  useCurrentUserStore().me = me({ orgs: [{ ...ACME }, { ...GLOBEX }] })
  const router = await testRouter(path)
  const seen: (string | null)[] = []
  const Page = defineComponent(() => {
    const org = useRouteOrg()
    watchEffect(() => seen.push(org.value?.name ?? null))
    return () => h('p', org.value?.name ?? 'none')
  })
  const wrapper = mount(Page, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router, seen }
}

beforeEach(() => setActivePinia(createPinia()))

describe('useRouteOrg', () => {
  it("is the org the URL's slug names, made the shell's current org", async () => {
    const { wrapper } = await mountAt('/globex/members')

    expect(wrapper.text()).toBe('Globex Retail')
    expect(useCurrentOrgStore().org?.slug).toBe('globex')
  })

  it("is null for a slug the user doesn't see", async () => {
    const { wrapper } = await mountAt('/initech/members')

    expect(wrapper.text()).toBe('none')
  })

  it('follows its org to a new slug, keeping the page and its query, never losing it', async () => {
    const { router, seen } = await mountAt('/acme/members?offset=25')

    useCurrentUserStore().me!.orgs[0]!.slug = 'acme-mfg'
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme-mfg/members?offset=25')
    expect(seen).not.toContain(null)
    expect(useCurrentOrgStore().org?.slug).toBe('acme-mfg')
  })

  it('keeps its org when /me reloads before the redirect lands', async () => {
    const { router, seen } = await mountAt('/acme/members')

    useCurrentUserStore().me!.orgs[0]!.slug = 'acme-mfg'
    await nextTick()
    useCurrentUserStore().me = me({ orgs: [{ ...ACME, slug: 'acme-mfg' }, { ...GLOBEX }] })
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/acme-mfg/members')
    expect(seen).not.toContain(null)
  })

  it("doesn't follow its org to a URL that names another, unknown slug", async () => {
    const { wrapper, router } = await mountAt('/acme/members')
    expect(wrapper.text()).toBe('Acme Manufacturing')

    await router.push('/initech/members')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/initech/members')
    expect(wrapper.text()).toBe('none')
  })
})
