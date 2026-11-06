/**
 * The people lists' shared pieces (Staff, an org's and a project's Members, Users): the
 * "Show deactivated" filter kept in the URL (DL-293, DL-295), and focus after an action that may
 * take a person off the list (UI-FRM-14).
 */
import { computed, nextTick, type Ref } from 'vue'
import { useRouter } from 'vue-router'

import { focusHeading } from '@/app/routeFocus'

import type { useListQuery } from './useListQuery'

type PeopleQuery = ReturnType<typeof useListQuery<'include_deactivated'>>

/** Whether deactivated people are asked for: only by the list's admins (`canShow`), so an old
 * link's `include_deactivated` from anyone else is ignored (DL-294). */
export function useShowDeactivated(query: PeopleQuery, canShow: () => boolean) {
  const router = useRouter()
  const show = computed(() => canShow() && query.filter.value.include_deactivated === 'true')
  function toggle(event: Event) {
    const checked = (event.target as HTMLInputElement).checked
    void router.replace(query.filtered({ include_deactivated: checked ? 'true' : '' }))
  }
  return { show, toggle }
}

/** Remembers the row an action ran on; once the list reloads, if that person has left it, focus
 * goes to the actions of the row now in its place, or the `h1` when there's none. A person still
 * listed keeps the focus the dialog returned to their row. */
export function useRefocusWhenGone(table: Ref<HTMLTableElement | undefined>) {
  let index = -1
  let id = ''
  function mark(at: number, userId: string) {
    index = at
    id = userId
  }
  async function settle(listed: readonly string[]) {
    if (listed.includes(id)) return
    await nextTick()
    const row = table.value?.querySelectorAll('tbody tr')[index]
    const actions = row?.querySelector<HTMLElement>('button[aria-haspopup=menu]')
    if (actions) actions.focus()
    else await focusHeading()
  }
  return { mark, settle }
}
