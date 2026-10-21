/**
 * The org an org page's URL names (`/:orgSlug/…`), from the user's orgs in `/me`, made the shell's
 * current org; null for a slug the user doesn't see, which the page shows as not found. When `/me`
 * gives the page's org a new slug (a slug change) and the URL hasn't moved, the page follows it to
 * the new URL (a stale slug redirects, DL-97).
 */
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useCurrentOrgStore } from '@/stores/currentOrg'

export function useRouteOrg() {
  const route = useRoute()
  const router = useRouter()
  const nav = useCurrentOrgStore()
  // The org this page last showed, and the slug its URL had then.
  let shown: { id: string; slug: string } | null = null

  const org = computed(() => {
    const slug = route.params.orgSlug
    const bySlug = nav.orgs.find((o) => o.slug === slug)
    if (bySlug || !shown || slug !== shown.slug) return bySlug ?? null
    const id = shown.id
    return nav.orgs.find((o) => o.id === id) ?? null
  })

  // The id and slug, not the entry: a slug change may edit the entry in place.
  watch(
    [() => org.value?.id, () => org.value?.slug],
    () => {
      const current = org.value
      if (!current) return
      // The URL's slug, not the org's: until a redirect lands, the old URL still finds the org.
      shown = { id: current.id, slug: String(route.params.orgSlug) }
      nav.enter(current.slug)
      if (current.slug !== route.params.orgSlug) {
        void router.replace({
          name: route.name!,
          params: { ...route.params, orgSlug: current.slug },
          query: route.query,
        })
      }
    },
    { immediate: true },
  )
  return org
}
