/** Mounting a workspace admin page for its spec (DL-104): signed in, with the workspace in `/me`. */
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import { afterEach, vi } from 'vitest'
import type { Component } from 'vue'

import { client } from '@/api/client'
import type { Action } from '@/composables/allowedActions'
import { type Me, useCurrentUserStore } from '@/stores/currentUser'

import { me, ok, workspaceEntry } from './api'
import { testRouter } from './router'

export const WORKSPACE_ID = workspaceEntry([]).id

/** `view` at `path`, for someone whose workspace entry carries `allowed`, in a `main`. */
export async function mountWorkspaceView(
  view: Component,
  path: string,
  allowed: Action[] = ['workspace.view'],
  workspaces = [workspaceEntry(allowed)],
) {
  return mountSignedIn(view, path, me({ workspaces }))
}

/** `view` at `path` for the user `signedIn`, in a `main`. */
export async function mountSignedIn(view: Component, path: string, signedIn: Me) {
  useCurrentUserStore().me = signedIn
  const router = await testRouter(path)
  const wrapper = mount(
    { components: { AdminPage: view }, template: '<main><AdminPage /></main>' },
    {
      global: { plugins: [router, PrimeVue], stubs: { transition: false } },
      attachTo: document.body,
    },
  )
  await flushPromises()
  return { wrapper, router }
}

/** The usual clean-up, unmounting before the body is cleared (frontend/CLAUDE.md, "Tests"). */
export function cleanUpAfterEach() {
  afterEach(() => {
    document.body.innerHTML = ''
  })
  enableAutoUnmount(afterEach)
}

/** Every GET answered with `first`, except a list page past the first, which is empty: a page
 * whose last row went (TD-58). */
export function emptyPastTheFirst(first: unknown) {
  return vi
    .spyOn(client, 'GET')
    .mockImplementation(((_: string, init?: { params?: { query?: { offset?: number } } }) =>
      Promise.resolve(ok(init?.params?.query?.offset ? listPage([], 1) : first))) as never)
}

/** A page of a list endpoint's answer. */
export function listPage<T>(items: T[], total = items.length) {
  return { items, total, limit: 25, offset: 0 }
}
