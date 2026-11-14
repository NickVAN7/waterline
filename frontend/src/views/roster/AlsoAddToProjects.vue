<script setup lang="ts">
// The org add's last step (Q12g, DL-379): the org's live projects (`GET …/member-projects`), each
// a checkbox; a chosen one gets a role (Member to start) and, when it's export-controlled, its own
// confirmation that the person is authorized (design-doc §3.1). The picks are the dialog's
// (`v-model`), which keeps them across its steps and clears the confirmations when the person
// changes. A failed load says so here, with Try again, not in the form's alert (UI-FRM-7): a
// failed Try again is a new alert (`failures`, `retried`), and one that loads puts focus on the
// first project, since its button goes (`focusFirst`). `note` says what a reload changed in the
// picks (one dropped, or now export-controlled), in a polite region always there.
import { nextTick, ref } from 'vue'

import Button from '@/components/Button.vue'
import Icon from '@/components/Icon.vue'
import SelectField from '@/components/SelectField.vue'
import Skeleton from '@/components/Skeleton.vue'

import type { MemberProject, ProjectPick, RoleOption } from './roster'

defineProps<{
  projects: MemberProject[] | undefined
  failed: boolean
  // Failed loads in a row, and whether the latest came from the user's Try again.
  failures: number
  retried: boolean
  loading: boolean
  roles: RoleOption[]
  note: string
}>()
const picks = defineModel<Record<string, ProjectPick>>({ required: true })
const emit = defineEmits<{ retry: [] }>()

const root = ref<HTMLFieldSetElement>()
/** After a Try again that loaded: the first project's box, or the "no projects" sentence. */
async function focusFirst() {
  await nextTick()
  root.value?.querySelector<HTMLElement>('input[type=checkbox], [data-no-projects]')?.focus()
}
defineExpose({ focusFirst })

function toggle(project: MemberProject, on: boolean) {
  const next = { ...picks.value }
  if (on)
    next[project.id] = {
      name: project.name,
      role: 'member',
      exportControlled: project.export_controlled,
      confirmed: false,
    }
  else delete next[project.id]
  picks.value = next
}

function update(id: string, change: Partial<ProjectPick>) {
  picks.value = { ...picks.value, [id]: { ...picks.value[id]!, ...change } }
}
</script>

<template>
  <fieldset
    ref="root"
    :aria-busy="loading && !projects ? 'true' : 'false'"
    class="m-0 flex flex-col gap-2 border-0 p-0"
  >
    <legend class="mb-2 font-medium">Also add to projects</legend>
    <div v-if="failed" class="flex flex-wrap items-center gap-3">
      <p
        :key="failures"
        :role="retried ? 'alert' : undefined"
        class="m-0 flex items-center gap-1 text-sm text-tone-danger-fg"
      >
        <Icon name="alert" />Couldn't load the organization's projects.
      </p>
      <Button variant="secondary" :pending="loading" pending-label="Loading…" @click="emit('retry')"
        >Try again</Button
      >
    </div>
    <Skeleton v-else-if="!projects" :rows="2" />
    <p
      v-else-if="!projects.length"
      data-no-projects
      tabindex="-1"
      class="m-0 text-sm text-text-muted"
    >
      The organization has no projects to add them to.
    </p>
    <!-- Its own scroll region past a few projects; the checkboxes inside are its Tab stops. -->
    <!-- Padded, so a focus ring isn't clipped by the scroll box (UI-TOK-5). -->
    <ul v-else role="list" class="-m-1 flex max-h-72 list-none flex-col gap-3 overflow-y-auto p-1">
      <li v-for="project in projects" :key="project.id" class="flex flex-col gap-2">
        <label class="flex items-start gap-2">
          <input
            type="checkbox"
            :checked="!!picks[project.id]"
            class="size-(--target-min) shrink-0"
            @change="toggle(project, ($event.target as HTMLInputElement).checked)"
          />
          <span
            >{{ project.name }}
            <span class="font-mono text-sm text-text-muted">{{ project.key }}</span></span
          >
        </label>
        <div v-if="picks[project.id]" class="flex flex-col gap-2 pl-8">
          <SelectField
            :id="`add-project-${project.id}-role`"
            :model-value="picks[project.id]!.role"
            :label="`Role on ${project.name}`"
            :options="roles"
            @update:model-value="update(project.id, { role: $event })"
          />
          <label v-if="project.export_controlled" class="flex items-start gap-2">
            <input
              type="checkbox"
              :checked="picks[project.id]!.confirmed"
              class="size-(--target-min) shrink-0"
              @change="
                update(project.id, { confirmed: ($event.target as HTMLInputElement).checked })
              "
            />
            <span
              >I confirm this person is authorized for {{ project.name }}'s export-controlled
              data.</span
            >
          </label>
        </div>
      </li>
    </ul>
    <p class="m-0 text-sm" aria-live="polite">{{ note }}</p>
  </fieldset>
</template>
