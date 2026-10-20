/**
 * A project page's project (`/{org_slug}/projects/{key}/…`; DL-97): loaded by its key, a stale or
 * wrong org slug or a lowercase key replaced with the project's own, then selected in the shell.
 * A project the user can't see is the not-found page, the same as one that doesn't exist
 * (UI-FBK-14). The route sets `meta.settlesItself`: the page settles once the `h1` is there.
 */
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, client } from '@/api/client'
import { focusHeading, redirectInPlace, settlePage } from '@/app/routeFocus'
import { useLoad } from '@/composables/useLoad'
import { useCurrentOrgStore } from '@/stores/currentOrg'

export function useProjectPage(routeName: 'project-home' | 'project-settings') {
  const route = useRoute()
  const router = useRouter()
  const nav = useCurrentOrgStore()

  const key = String(route.params.key)
  const project = useLoad(() =>
    api(client.GET('/api/projects/{key}', { params: { path: { key: key.toUpperCase() } } })),
  )
  const notFound = computed(() => project.error.value?.status === 404)

  /** Once loaded: the project's own URL, or it becomes the selected project. False if redirected. */
  async function opened(): Promise<boolean> {
    const loaded = project.data.value
    if (!loaded) return true
    const orgSlug = nav.orgs.find((o) => o.id === loaded.organization_id)?.slug
    if (orgSlug && (orgSlug !== route.params.orgSlug || key !== loaded.key)) {
      await redirectInPlace(() =>
        router.replace({ name: routeName, params: { orgSlug, key: loaded.key } }),
      )
      return false
    }
    nav.select(loaded)
    return true
  }

  onMounted(async () => {
    await project.run()
    if (await opened()) await settlePage()
  })

  // Try again (UI-FBK-15): focus goes to the `h1` once it loads.
  async function retry() {
    if ((await project.run()) && (await opened())) await focusHeading()
  }

  return { key, project, notFound, retry }
}
