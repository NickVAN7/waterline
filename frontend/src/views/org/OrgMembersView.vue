<script setup lang="ts">
// An org's members (`/{org_slug}/members`; build plan, "The org members API"), on the shared roster
// page: its endpoints, roles, and who may open it (`org_member.manage`). An org slug the user
// doesn't see is the not-found page.
import { computed, ref } from 'vue'

import { api, client } from '@/api/client'
import type { components } from '@/api/schema'
import { orgCrumb } from '@/app/crumbs'
import { ORG_ROLE, PROJECT_ROLE } from '@/app/labels'
import { allows } from '@/composables/allowedActions'
import { useRouteOrg } from '@/composables/useRouteOrg'
import NotFoundView from '@/views/errors/NotFoundView.vue'
import RosterPage from '@/views/roster/RosterPage.vue'
import type { AddOptions, Roster } from '@/views/roster/roster'

import { WHO_TO_ASK } from './orgAdmin'

type Role = components['schemas']['OrgRole']
type ProjectRole = components['schemas']['ProjectRole']

const org = useRouteOrg()
// The org's workspace, for the user check (DL-66): `/me` lists an org without it. There's one
// workspace (design-doc §4), so it holds across orgs.
const workspaceId = ref('')

const path = () => ({ org_id: org.value!.id })
// The org add's last step (DL-379): each chosen project, its confirmation only where the list
// loaded it export-controlled. Cast: the schema types the confirmation as always sent (it has a
// default), but the server refuses it where none is needed (`confirmation_not_needed`).
const projectsOf = (options: AddOptions) =>
  Object.entries(options.projects).map(
    ([project_id, pick]) =>
      ({
        project_id,
        role: pick.role as ProjectRole,
        ...(pick.exportControlled ? { export_control_confirmed: pick.confirmed } : {}),
      }) as components['schemas']['MemberProjectAdd'],
  )
const roster = computed<Roster>(() => ({
  scope: org.value?.name ?? '',
  projects: `${org.value?.name ?? ''}'s projects`,
  roles: (Object.keys(ORG_ROLE) as Role[]).map((value) => ({ value, label: ORG_ROLE[value] })),
  workspaceId: workspaceId.value,
  add: (email, role, options) =>
    api(
      client.POST('/api/orgs/{org_id}/members', {
        params: { path: path() },
        body: { email, role: role as Role, projects: projectsOf(options) },
      }),
    ),
  create: (person, options) =>
    api(
      client.POST('/api/orgs/{org_id}/members/new', {
        params: { path: path() },
        body: { ...person, role: person.role as Role, projects: projectsOf(options) },
      }),
    ),
  memberProjects: async () =>
    (
      await api(
        client.GET('/api/orgs/{org_id}/member-projects', {
          // The list cap, which the add's `projects` limit matches (TD-115).
          params: { path: path(), query: { limit: 200 } },
        }),
      )
    ).items,
  projectRoles: (Object.keys(PROJECT_ROLE) as ProjectRole[]).map((value) => ({
    value,
    label: PROJECT_ROLE[value],
  })),
  changeRole: (userId, role, newOwnerId) =>
    api(
      client.PATCH('/api/orgs/{org_id}/members/{user_id}', {
        params: { path: { ...path(), user_id: userId } },
        body: { role: role as Role, ...(newOwnerId ? { new_owner_id: newOwnerId } : {}) },
      }),
    ),
  remove: (userId, withProjects, newOwnerId) =>
    api(
      client.DELETE('/api/orgs/{org_id}/members/{user_id}', {
        params: {
          path: { ...path(), user_id: userId },
          query: {
            with_projects: withProjects,
            ...(newOwnerId ? { new_owner_id: newOwnerId } : {}),
          },
        },
      }),
    ),
  everyone: async () =>
    (
      await api(
        client.GET('/api/orgs/{org_id}/members', {
          params: { path: path(), query: { limit: 200 } },
        }),
      )
    ).items,
}))

// The workspace comes first, so the rows and Add person (and their dialogs) appear only once the
// user check can run; a failure of either is the list's error, with Try again.
async function list(query: { limit: number; offset: number; include_deactivated?: boolean }) {
  if (!workspaceId.value) {
    workspaceId.value = (
      await api(client.GET('/api/orgs/{org_id}', { params: { path: path() } }))
    ).workspace_id
  }
  return api(client.GET('/api/orgs/{org_id}/members', { params: { path: path(), query } }))
}
</script>

<template>
  <!-- An org the user doesn't see, or one they've lost since `/me` loaded (UI-FBK-14). -->
  <NotFoundView v-if="!org" />
  <RosterPage
    v-else
    :key="org.id"
    :title="`${org.name} members`"
    :crumbs="[orgCrumb(org), { label: 'Members' }]"
    list-name="Members"
    thing="the members"
    :roster="roster"
    :list="list"
    manage="org_member.manage"
    remove-label="Remove from organization"
    :role-labels="ORG_ROLE"
    :can-add="allows(org, 'org_member.manage') && workspaceId !== ''"
    :allowed="allows(org, 'org_member.manage')"
    :can-show-deactivated="allows(org, 'org_member.manage')"
    :who-to-ask="WHO_TO_ASK"
    hidden
  >
  </RosterPage>
</template>
