<script setup lang="ts">
// One organization's projects on My work (DL-329, DL-330, DL-349, DL-359): its heading (the org's
// name, or "Projects" when it's the user's only org) with how many projects of it they can open,
// its first open projects ("Showing 5 of N" past them, DL-368), a "Show N hidden projects" toggle for
// its completed, cancelled, and archived ones, and "All N projects", its org list, counted as
// that list counts (all but the archived), left out when that's none.
import { computed, ref } from 'vue'

import type { components } from '@/api/schema'
import Button from '@/components/Button.vue'

import MyProjectRows from './MyProjectRows.vue'

type MyProject = components['schemas']['MyProjectItem']

const props = defineProps<{
  /** The section's id, its heading's `${id}-heading`. */
  id: string
  org: components['schemas']['OrgWork']
  heading: string
  starring: string
  /** The page is reloading (after a star): the section is busy, as `MyWorkSection`'s are. */
  loading: boolean
}>()
defineEmits<{ toggle: [list: string, project: MyProject, index: number] }>()

const showHidden = ref(false)
const projectsCount = (n: number) => (n === 1 ? '1 project' : `${n} projects`)
const hiddenCount = computed(() =>
  props.org.hidden_total === 1 ? '1 hidden project' : `${props.org.hidden_total} hidden projects`,
)
// Each list's stars are named apart, so focus returns to the right one after a star change.
const openList = computed(() => `org-${props.org.id}`)
const hiddenList = computed(() => `org-${props.org.id}-hidden`)
</script>

<template>
  <section
    :aria-labelledby="`${id}-heading`"
    :aria-busy="loading ? 'true' : 'false'"
    class="flex flex-col gap-3"
  >
    <div class="flex flex-wrap items-baseline gap-x-3">
      <h2 :id="`${id}-heading`" class="m-0 text-lg font-semibold">{{ heading }}</h2>
      <span class="text-sm text-text-muted">{{ projectsCount(org.total + org.hidden_total) }}</span>
    </div>
    <MyProjectRows
      v-if="org.projects.length"
      :projects="org.projects"
      :list="openList"
      :starring="starring"
      @toggle="(project, index) => $emit('toggle', openList, project, index)"
    />
    <p v-if="org.total > org.projects.length" class="m-0 text-sm text-text-muted">
      Showing {{ org.projects.length }} of {{ org.total }}
    </p>
    <template v-if="org.hidden_total">
      <!-- The house disclosure, as RevisionCompare's "Show N unchanged lines" (UI-TOK-6). -->
      <Button
        variant="ghost"
        class="self-start"
        :aria-expanded="showHidden ? 'true' : 'false'"
        :aria-controls="`${id}-hidden`"
        @click="showHidden = !showHidden"
        >{{ showHidden ? 'Hide' : 'Show' }} {{ hiddenCount }}</Button
      >
      <div v-show="showHidden" :id="`${id}-hidden`" class="flex flex-col gap-3">
        <MyProjectRows
          :projects="org.hidden"
          :list="hiddenList"
          :starring="starring"
          @toggle="(project, index) => $emit('toggle', hiddenList, project, index)"
        />
        <p v-if="org.hidden_total > org.hidden.length" class="m-0 text-sm text-text-muted">
          Showing {{ org.hidden.length }} of {{ org.hidden_total }} hidden projects
        </p>
      </div>
    </template>
    <!-- None when the org's list would show nothing: every project here is archived (DL-359). -->
    <RouterLink
      v-if="org.listed_total"
      :to="{ name: 'org-projects', params: { orgSlug: org.slug } }"
      class="inline-flex min-h-(--target-min) items-center self-start text-sm"
      >All {{ projectsCount(org.listed_total) }}</RouterLink
    >
  </section>
</template>
