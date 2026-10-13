/**
 * After each navigation (UI-SHL-9): the title becomes `<h1 text> · Waterline`, and focus moves to
 * the new page's `h1`, except on the first page load (no autofocus on load, UI-FRM-16).
 */
import { nextTick } from 'vue'
import { START_LOCATION, type Router } from 'vue-router'

export const APP_NAME = 'Waterline'

export function installRouteFocus(router: Router): void {
  router.afterEach(async (to, from, failure) => {
    if (failure) return
    await nextTick()
    const heading = document.querySelector<HTMLElement>('main h1')
    document.title = heading?.textContent ? `${heading.textContent.trim()} · ${APP_NAME}` : APP_NAME
    if (heading && from !== START_LOCATION) {
      heading.tabIndex = -1
      heading.focus()
    }
  })
}
