<script setup lang="ts">
// A project's members (`/{org_slug}/projects/{key}/members`; build plan, "The project members
// API"), on the shared roster page. Anyone who sees the project reads the list (`project.view`);
// its admins (`project_member.manage`) add from the picker or by email (an account from outside
// the org joins it too, `join_org`, DL-78), change roles, and remove, with no last-admin guard
// (DL-71). On an export-controlled project every add confirms the person is authorized
// (design-doc §3.1). Its admins also open the access review (`project.view_access`). Loading, the
// not-found page, and the redirect are `useProjectPage`'s.
import { computed, ref } from 'vue'

import { api, client } from '@/api/client'
import type { components } from '@/api/schema'
import { PROJECT_ROLE } from '@/app/labels'
import { focusHeading, settlePage } from '@/app/routeFocus'
import Button from '@/components/Button.vue'
import ErrorState from '@/components/ErrorState.vue'
import Skeleton from '@/components/Skeleton.vue'
import { allows } from '@/composables/allowedActions'
import { useCurrentOrgStore } from '@/stores/currentOrg'
import NotFoundView from '@/views/errors/NotFoundView.vue'
import RosterPage from '@/views/roster/RosterPage.vue'
import type { AddOptions, Roster } from '@/views/roster/roster'

import AddMemberDialog from './AddMemberDialog.vue'
import ProjectHeader from './ProjectHeader.vue'
import { useProjectPage } from './useProjectPage'

type Role = components['schemas']['ProjectRole']

// Only if the list itself is refused; a project the user can't see is the not-found page.
const WHO_TO_ASK = "Ask one of the project's admins if you need to see its members."

const { key, project, notFound, retry } = useProjectPage('project-members')
const nav = useCurrentOrgStore()
const loaded = computed(() => project.data.value)
const canManage = computed(() => allows(loaded.value, 'project_member.manage'))
// The project's workspace, for the add-person form's user check (DL-66); the project read has
// only its org.
const workspaceId = ref('')
const picker = ref<InstanceType<typeof AddMemberDialog>>()

const path = () => ({ key: loaded.value!.key })
// The server refuses a confirmation where none is needed (`confirmation_not_needed`), so each is
// sent only when given. Cast: the schema types them as always sent (they have defaults).
const confirmations = (options: AddOptions) => ({
  ...(options.joinOrg ? { join_org: true } : {}),
  ...(options.exportControlConfirmed ? { export_control_confirmed: true } : {}),
})
const roster = computed<Roster>(() => ({
  scope: 'the project',
  roles: (Object.keys(PROJECT_ROLE) as Role[]).map((value) => ({
    value,
    label: PROJECT_ROLE[value],
  })),
  exportControlled: !!loaded.value?.restriction_categories.includes('export_controlled'),
  workspaceId: workspaceId.value,
  add: (email, role, options) =>
    api(
      client.POST('/api/projects/{key}/members', {
        params: { path: path() },
        body: {
          email,
          role: role as Role,
          ...confirmations(options),
        } as components['schemas']['ProjectMemberAdd'],
      }),
    ),
  create: (person, options) =>
    api(
      client.POST('/api/projects/{key}/members/new', {
        params: { path: path() },
        body: {
          ...person,
          role: person.role as Role,
          ...confirmations({ ...options, joinOrg: false }),
        } as components['schemas']['ProjectMemberCreate'],
      }),
    ),
  changeRole: (userId, role) =>
    api(
      client.PATCH('/api/projects/{key}/members/{user_id}', {
        params: { path: { ...path(), user_id: userId } },
        body: { role: role as Role },
      }),
    ),
  remove: (userId) =>
    api(
      client.DELETE('/api/projects/{key}/members/{user_id}', {
        params: { path: { ...path(), user_id: userId } },
      }),
    ),
}))

// For its admins, the workspace comes first, so Add by email (and its dialog) appears only once
// the user check can run; a failure of either is the list's error, with Try again.
async function list(query: { limit: number; offset: number }) {
  if (canManage.value && !workspaceId.value) {
    workspaceId.value = (
      await api(
        client.GET('/api/orgs/{org_id}', {
          params: { path: { org_id: loaded.value!.organization_id } },
        }),
      )
    ).workspace_id
  }
  return api(client.GET('/api/projects/{key}/members', { params: { path: path(), query } }))
}

// A 403 in a dialog: the project's actions changed too (its buttons, the export-control flag). If
// the project is gone with them, the page settles as a navigation does (UI-SHL-9).
async function refused() {
  await project.run()
  if (project.data.value) nav.select(project.data.value)
  if (notFound.value) await settlePage()
}
</script>

<template>
  <NotFoundView v-if="notFound" />
  <div v-else class="flex flex-col gap-6">
    <div
      v-if="!loaded"
      class="flex flex-col gap-6"
      :aria-busy="project.loading.value ? 'true' : 'false'"
    >
      <template v-if="project.error.value">
        <h1 class="m-0 text-2xl leading-tight font-semibold font-mono">{{ key.toUpperCase() }}</h1>
        <ErrorState
          :key="project.failures.value"
          :live="project.failures.value > 1"
          thing="this project"
          :pending="project.loading.value"
          @retry="retry"
        />
      </template>
      <Skeleton v-else :rows="4" />
    </div>
    <RosterPage
      v-else
      :key="loaded.id"
      :title="`${loaded.name} members`"
      list-name="Members"
      thing="the members"
      :roster="roster"
      :list="list"
      manage="project_member.manage"
      remove-label="Remove from project"
      :role-labels="PROJECT_ROLE"
      allowed
      :who-to-ask="WHO_TO_ASK"
      hidden
      @refused="refused"
    >
      <template #header="{ add }">
        <ProjectHeader :project="loaded" :title="`${loaded.name} members`">
          <Button v-if="canManage" @click="picker?.open()">Add member</Button>
          <Button v-if="canManage && workspaceId" variant="secondary" @click="add()"
            >Add by email</Button
          >
          <RouterLink
            v-if="allows(loaded, 'project.view_access')"
            :to="{
              name: 'project-access',
              params: { orgSlug: $route.params.orgSlug, key: loaded.key },
            }"
            >Access review</RouterLink
          >
        </ProjectHeader>
      </template>
      <template #dialogs="{ done, refused: reload }">
        <!-- Mounted whatever the actions: a 403 reload mustn't take it away while it's open. -->
        <AddMemberDialog
          ref="picker"
          :fallback-focus="focusHeading"
          :project-key="loaded.key"
          :roles="roster.roles"
          :export-controlled="!!roster.exportControlled"
          @done="done"
          @refused="reload"
        />
      </template>
    </RosterPage>
    <!-- Outside the busy region, where a screen reader holds changes back until it's done. -->
    <p class="sr-only" aria-live="polite">
      {{ project.loading.value && !loaded ? 'Loading the project…' : '' }}
    </p>
  </div>
</template>
