/**
 * A list's state kept in the URL's query string (build plan, "API conventions"), so a reload, a
 * shared link, or Back shows the same page. Changing it is a query-only navigation, which doesn't
 * move focus (UI-SHL-9). Paging only, until a list sorts or filters (S1-C16, Slice 3).
 */
import { computed } from 'vue'
import { type RouteLocationRaw, useRoute } from 'vue-router'

export function useListQuery({ limit }: { limit: number }) {
  const route = useRoute()

  const offset = computed(() => {
    const value = Number(route.query.offset)
    return Number.isInteger(value) && value > 0 ? value : 0
  })
  const params = computed(() => ({ limit, offset: offset.value }))

  /** Where the list is at `next`: the same page's query with the new offset. */
  function linkTo(next: number): RouteLocationRaw {
    return { query: { ...route.query, offset: next > 0 ? String(next) : undefined } }
  }

  return { params, offset, limit, linkTo }
}
