/** Mounting an org admin page for its spec (DL-104): signed in, with the org in `/me`. */
import { flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import type { Component } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import { installRouteFocus } from '@/app/routeFocus'
import type { Action } from '@/composables/allowedActions'
import { useCurrentUserStore } from '@/stores/currentUser'
import OrgMembersView from '@/views/org/OrgMembersView.vue'
import OrgSettingsView from '@/views/org/OrgSettingsView.vue'

import { ACME, me } from './api'
import { mountSignedIn } from './workspace'

/** `ACME` (slug `acme`) with the org-level actions its admin page needs. */
export function acme(allowed: Action[]) {
  return { ...ACME, role: 'admin' as const, allowed_actions: allowed }
}

/** `view` at `path`, for someone whose only org is `acme` with `allowed`. */
export function mountOrgView(view: Component, path: string, allowed: Action[]) {
  return mountSignedIn(view, path, me({ orgs: [acme(allowed)] }))
}

/**
 * The org admin pages at `path` behind a `RouterView` keyed on the path, with the app's route
 * focus, as `App.vue` has it: a change of path (a slug change) remounts the page and focuses its
 * `h1`, as in the app.
 */
export async function mountOrgPages(path: string, allowed: Action[]) {
  useCurrentUserStore().me = me({ orgs: [acme(allowed)] })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/:orgSlug/members', name: 'org-members', component: OrgMembersView },
      { path: '/:orgSlug/settings', name: 'org-settings', component: OrgSettingsView },
    ],
  })
  installRouteFocus(router)
  await router.push(path)
  const wrapper = mount(
    { template: '<main><RouterView :key="$route.path" /></main>' },
    {
      global: { plugins: [router, PrimeVue], stubs: { transition: false } },
      attachTo: document.body,
    },
  )
  await flushPromises()
  return { wrapper, router }
}
