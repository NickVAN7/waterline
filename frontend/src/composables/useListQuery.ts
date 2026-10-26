/**
 * A list's state kept in the URL's query string (build plan, "API conventions"), so a reload, a
 * shared link, or Back shows the same page. Changing it is a query-only navigation, which doesn't
 * move focus (UI-SHL-9). Paging, and the fixed filters a list names (the org's project list's
 * status and type, S1-C16); sorting comes with the first sortable list (Slice 3).
 */
import { computed, type Ref, watch } from 'vue'
import { type RouteLocationRaw, useRoute, useRouter } from 'vue-router'

export function useListQuery<F extends string = never>({
  limit,
  filters = [],
  offsetKey = 'offset',
}: {
  limit: number
  filters?: readonly F[]
  // The URL's name for this list's offset: a page with two paged lists names one apart.
  offsetKey?: string
}) {
  const route = useRoute()
  const router = useRouter()

  const offset = computed(() => {
    const value = Number(route.query[offsetKey])
    return Number.isInteger(value) && value > 0 ? value : 0
  })

  /** Each filter's value from the URL, or '' when it isn't set. */
  const filter = computed(
    () =>
      Object.fromEntries(
        filters.map((name) => {
          const value = route.query[name]
          return [name, typeof value === 'string' ? value : '']
        }),
      ) as Record<F, string>,
  )

  const active = computed(() =>
    Object.fromEntries(Object.entries(filter.value).filter(([, value]) => value !== '')),
  )

  // The query as strings, and the key a view watches to reload. A view whose API wants another
  // shape (the project list's one-item lists) builds its request from `filter`.
  const params = computed(() => ({ limit, offset: offset.value, ...active.value }))

  /** Where the list is at `next`: the same page's query with the new offset. */
  function linkTo(next: number): RouteLocationRaw {
    return { query: { ...route.query, [offsetKey]: next > 0 ? String(next) : undefined } }
  }

  /** The list with these filters changed ('' clears one), from its first page. */
  function filtered(changes: Partial<Record<F, string>>): RouteLocationRaw {
    const query: Record<string, unknown> = { ...route.query, [offsetKey]: undefined }
    for (const [name, value] of Object.entries(changes)) query[name] = value || undefined
    return { query } as RouteLocationRaw
  }

  const filtering = computed(() => Object.keys(active.value).length > 0)

  /** A loaded page past the end (an old link, or the last page's last row removed) goes back to
   * the first (TD-58). */
  function returnWhenEmpty(page: Ref<{ items: readonly unknown[] } | undefined>) {
    watch(page, (loaded) => {
      if (loaded && !loaded.items.length && offset.value > 0) void router.replace(linkTo(0))
    })
  }

  return { params, offset, limit, linkTo, filter, filtered, filtering, returnWhenEmpty }
}
