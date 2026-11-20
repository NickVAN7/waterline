import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { client } from '@/api/client'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import { useCurrentUserStore } from '@/stores/currentUser'
import { failed, me, ok } from '@/test/api'
import { project } from '@/test/projects'

import { useProjectPage } from './useProjectPage'

const NOT_FOUND = failed(404, { code: 'not_found', message: 'Not found.', details: {} })
const EXPORT =
  "This project's content is export-controlled: only its members can read it. Ask one of its admins to add you."
const OWN = "Ask one of the project's admins if you need its requirements."

// A project page reduced to what the composable gives it: the not-found page, or the project's
// `h1` with an action button that keeps focus while the page stays.
let page!: ReturnType<typeof useProjectPage>
const Host = defineComponent({
  setup() {
    page = useProjectPage('project-home')
    return page
  },
  template: `
    <h1 v-if="notFound">Page not found</h1>
    <template v-else-if="project.data.value">
      <h1>{{ project.data.value.name }}</h1>
      <button type="button">Act</button>
    </template>`,
})

async function mountHost() {
  useCurrentUserStore().me = me()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:orgSlug/projects/:key', name: 'project-home', component: Host }],
  })
  await router.push('/acme/projects/ERP')
  const wrapper = mount(
    { template: '<main><RouterView /></main>' },
    { global: { plugins: [router] }, attachTo: document.body },
  )
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('useProjectPage', () => {
  describe('reload', () => {
    it('reads the project again and leaves focus where it was while the page stays', async () => {
      const get = vi
        .spyOn(client, 'GET')
        .mockResolvedValueOnce(ok(project()))
        .mockResolvedValueOnce(ok(project({ name: 'ERP renamed' })))
      const wrapper = await mountHost()
      const act = wrapper.get('button').element
      act.focus()

      expect(await page.reload()).toBe(true)
      await flushPromises()

      expect(get).toHaveBeenCalledTimes(2)
      expect(useCurrentOrgStore().project?.name).toBe('ERP renamed')
      expect(document.activeElement).toBe(act)
    })

    it('settles on the not-found page when the project has gone (UI-SHL-9)', async () => {
      vi.spyOn(client, 'GET').mockResolvedValueOnce(ok(project())).mockResolvedValueOnce(NOT_FOUND)
      const wrapper = await mountHost()
      wrapper.get('button').element.focus()

      expect(await page.reload()).toBe(false)

      expect(document.activeElement).toBe(wrapper.get('h1').element)
      expect(wrapper.get('h1').text()).toBe('Page not found')
      expect(document.title).toBe('Page not found · Waterline')
    })

    it("settles on the page's new h1 when the page says it's no longer shown", async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(ok(project()))
      const wrapper = await mountHost()
      wrapper.get('button').element.focus()

      document.title = 'Stale'

      expect(await page.reload(() => false)).toBe(false)

      expect(document.activeElement).toBe(wrapper.get('h1').element)
      expect(document.title).toBe('ERP rollout · Waterline')
    })
  })

  describe('whoToAsk', () => {
    it("is the page's own sentence on a project that isn't export-controlled", async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(ok(project({ restriction_categories: ['pii'] })))
      await mountHost()

      expect(page.exportControlled.value).toBe(false)
      expect(page.whoToAsk(OWN)).toBe(OWN)
    })

    it('points to membership on an export-controlled project (design-doc §3.1)', async () => {
      vi.spyOn(client, 'GET').mockResolvedValue(
        ok(project({ restriction_categories: ['export_controlled'] })),
      )
      await mountHost()

      expect(page.exportControlled.value).toBe(true)
      expect(page.whoToAsk(OWN)).toBe(EXPORT)
    })
  })
})
