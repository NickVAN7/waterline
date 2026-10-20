/**
 * After each navigation (UI-SHL-9): the title becomes `<h1 text> · Waterline`, and focus moves to
 * the new page's `h1`, except on the first page load (no autofocus on load, UI-FRM-16). A change
 * to the query alone (a list's page, through `useListQuery`) does neither: the list announces its
 * new count instead. A page whose `h1` waits for its data (`meta.settlesItself`) calls
 * `settlePage()` once it has loaded.
 */
import { nextTick } from 'vue'
import { START_LOCATION, type Router } from 'vue-router'

export const APP_NAME = 'Waterline'

let firstPage = true
let redirecting = false

function heading(): HTMLElement | null {
  return document.querySelector<HTMLElement>('main h1')
}

/** Focus the page's `h1` (after Try again succeeds, UI-FBK-15). */
export async function focusHeading(): Promise<void> {
  await nextTick()
  const h1 = heading()
  if (!h1) return
  h1.tabIndex = -1
  h1.focus()
}

/** A page replacing its own URL as it loads (a project's stale slug): the page that follows is
 * still the first one, if it was. */
export async function redirectInPlace(go: () => Promise<unknown>): Promise<void> {
  redirecting = true
  try {
    await go()
  } finally {
    redirecting = false
  }
}

/** Set the title from the `h1`, for a page whose `h1` changed in place (a rename). */
export async function syncTitle(): Promise<void> {
  await nextTick()
  const h1 = heading()
  document.title = h1?.textContent ? `${h1.textContent.trim()} · ${APP_NAME}` : APP_NAME
}

/** Set the title from the `h1` and, after the first page, focus it. */
export async function settlePage(): Promise<void> {
  await syncTitle()
  if (!firstPage) await focusHeading()
}

export function installRouteFocus(router: Router): void {
  router.afterEach(async (to, from, failure) => {
    if (failure) return
    if (from !== START_LOCATION && to.path === from.path) return
    firstPage = from === START_LOCATION || (firstPage && redirecting)
    if (!to.meta.settlesItself) await settlePage()
  })
}
