/**
 * Which org the shell is in (the org menu, UI-SHL-4) and the selected project (the project
 * selector, UI-SHL-6). An org page sets the org from its URL; elsewhere the last one stays, or the
 * user's first org. A project page sets the project.
 */
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

import type { components } from '@/api/schema'

import { useCurrentUserStore } from './currentUser'

export type Project = components['schemas']['ProjectRead']

export const useCurrentOrgStore = defineStore('currentOrg', () => {
  const user = useCurrentUserStore()
  const slug = ref<string | null>(null)
  const project = ref<Project | null>(null)

  const orgs = computed(() => user.me?.orgs ?? [])
  const org = computed(() => orgs.value.find((o) => o.slug === slug.value) ?? orgs.value[0] ?? null)

  function enter(orgSlug: string): void {
    slug.value = orgSlug
    if (project.value && project.value.organization_id !== org.value?.id) project.value = null
  }

  function select(selected: Project): void {
    project.value = selected
    slug.value = orgs.value.find((o) => o.id === selected.organization_id)?.slug ?? slug.value
  }

  // A different user (or nobody) starts with nothing selected.
  watch(
    () => user.me?.user.id,
    () => {
      slug.value = null
      project.value = null
    },
  )

  return { org, orgs, project, enter, select }
})
