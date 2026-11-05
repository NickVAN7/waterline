<script setup lang="ts">
// My work, the home page after sign-in (design-doc §11): one request for every section
// (`GET /api/me/work`): the projects, the approvals waiting for the user (DL-236), and their
// past decisions (DL-286), each with its first items and a total.
import { computed, onMounted, ref } from 'vue'

import { api, client } from '@/api/client'
import { focusHeading } from '@/app/routeFocus'
import { APPROVAL_DECISION, APPROVAL_REQUEST_STATUS } from '@/app/labels'
import Badge from '@/components/Badge.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useLoad } from '@/composables/useLoad'
import ProjectList from '@/views/project/ProjectList.vue'

import MyWorkSection from './MyWorkSection.vue'
import WorkItemHeading from './WorkItemHeading.vue'

// A failed request is one error state for the page; a section the server couldn't read comes
// back unavailable and gets its own, so the other sections still show (TD-40). Failed loads in a
// row, of either kind, key those states, so a failed Try again is a new alert. Only one of them
// announces itself and takes focus: the one whose Try again was pressed, if it failed again,
// otherwise the first (UI-FBK-15).
type Section = 'projects' | 'approvals' | 'decisions'
type Part = 'page' | Section
const PARTS: Part[] = ['page', 'projects', 'approvals', 'decisions']
const work = useLoad(() => api(client.GET('/api/me/work')))
const sections = computed(() => work.data.value?.sections)
const failedPart = (part: Part) =>
  part === 'page'
    ? Boolean(work.error.value)
    : !work.error.value && sections.value?.[part].available === false
const failed = computed(() => PARTS.some(failedPart))
const failures = ref(0)
const alerting = ref<Part>()

async function load(pressed?: Part) {
  await work.run()
  failures.value = failed.value ? failures.value + 1 : 0
  alerting.value = pressed && failedPart(pressed) ? pressed : PARTS.find(failedPart)
}
onMounted(() => load())
const live = (part: Part) => failures.value > 1 && alerting.value === part

// Focus moves to the `h1` once everything has loaded: the Try again pressed is then gone.
async function retry(pressed: Part) {
  await load(pressed)
  if (!failed.value) await focusHeading()
}

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const day = (at: string) => dateFormat.format(new Date(at))

const count = (n: number, one: string, many: string) => (n === 1 ? `1 ${one}` : `${n} ${many}`)
const announcement = computed(() => {
  if (work.loading.value) return 'Loading your work…'
  const { projects, approvals } = sections.value ?? {}
  return [
    projects?.available && count(projects.total, 'project', 'projects'),
    approvals?.available &&
      count(approvals.total, 'approval waiting for you', 'approvals waiting for you'),
  ]
    .filter(Boolean)
    .join(', ')
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <PageHeader title="My work" />
    <ErrorState
      v-if="work.error.value"
      :key="failures"
      :live="live('page')"
      thing="your work"
      :pending="work.loading.value"
      @retry="retry('page')"
    />
    <template v-else>
      <MyWorkSection
        id="projects"
        heading="Projects"
        thing="your projects"
        empty-heading="No projects yet"
        :section="sections?.projects"
        :loading="work.loading.value"
        :failures="failures"
        :live="live('projects')"
        @retry="retry('projects')"
      >
        <template #empty>Projects you're added to will appear here.</template>
        <template #default="{ items, total }">
          <ProjectList :projects="items" with-access />
          <!-- shortcut: no "see all" list yet (TD-37); the org's project list shows the rest. -->
          <p v-if="total > items.length" class="m-0 text-sm text-text-muted">
            Showing {{ items.length }} of {{ total }} projects. Each organization's project list has
            the rest.
          </p>
        </template>
      </MyWorkSection>

      <MyWorkSection
        id="approvals"
        heading="Approvals waiting for you"
        thing="your approvals"
        empty-heading="Nothing to decide"
        :section="sections?.approvals"
        :loading="work.loading.value"
        :failures="failures"
        :live="live('approvals')"
        @retry="retry('approvals')"
      >
        <template #empty>Approval requests that name you will appear here.</template>
        <template #default="{ items, total }">
          <ul class="m-0 flex list-none flex-col gap-2 p-0">
            <li
              v-for="item in items"
              :key="item.request_id"
              class="flex flex-col gap-1 rounded-lg border border-border-subtle bg-surface-raised p-3"
            >
              <WorkItemHeading :item="item" />
              <p class="m-0 text-sm text-text-muted">
                Requested by {{ item.requested_by_name }} on {{ day(item.requested_at) }}
              </p>
              <p v-if="item.note" class="m-0 whitespace-pre-line break-words text-sm">
                Note: {{ item.note }}
              </p>
            </li>
          </ul>
          <!-- shortcut: no "see all" list yet (TD-37). -->
          <p v-if="total > items.length" class="m-0 text-sm text-text-muted">
            Showing the {{ items.length }} oldest of {{ total }} approvals.
          </p>
        </template>
      </MyWorkSection>

      <MyWorkSection
        id="decisions"
        heading="My past decisions"
        thing="your past decisions"
        empty-heading="No decisions yet"
        :section="sections?.decisions"
        :loading="work.loading.value"
        :failures="failures"
        :live="live('decisions')"
        @retry="retry('decisions')"
      >
        <template #empty>Requests you approve or reject will appear here.</template>
        <template #default="{ items, total }">
          <ul class="m-0 flex list-none flex-col gap-2 p-0">
            <li
              v-for="item in items"
              :key="item.request_id"
              class="flex flex-col gap-1 rounded-lg border border-border-subtle bg-surface-raised p-3"
            >
              <WorkItemHeading :item="item">
                <Badge
                  class="ml-auto"
                  :tone="APPROVAL_DECISION[item.decision].tone"
                  :icon="APPROVAL_DECISION[item.decision].icon"
                >
                  <span class="sr-only">Your decision: </span
                  >{{ APPROVAL_DECISION[item.decision].label }}
                </Badge>
              </WorkItemHeading>
              <p class="m-0 text-sm text-text-muted">
                Decided on {{ day(item.decided_at) }}. Request:
                {{ APPROVAL_REQUEST_STATUS[item.request_status].label }}
              </p>
              <p v-if="item.comment" class="m-0 whitespace-pre-line break-words text-sm">
                Your comment: {{ item.comment }}
              </p>
            </li>
          </ul>
          <!-- shortcut: no "see all" list yet (TD-37). -->
          <p v-if="total > items.length" class="m-0 text-sm text-text-muted">
            Showing the {{ items.length }} newest of {{ total }} decisions.
          </p>
        </template>
      </MyWorkSection>
    </template>
    <!-- Outside the busy regions, where a screen reader holds changes back until it's done. -->
    <p class="sr-only" aria-live="polite">{{ announcement }}</p>
  </div>
</template>
