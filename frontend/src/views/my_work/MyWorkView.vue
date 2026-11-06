<script setup lang="ts">
// My work, the home page after sign-in (design-doc §11): one request for every section
// (`GET /api/me/work`): the favorite projects (DL-302), the projects, the approvals waiting for
// the user (DL-236), and their past decisions (DL-286), each with its first items and a total.
// A project row's star (DL-305) stars or unstars it, then the page reloads; focus stays on the
// star pressed, or, when its row left the list, goes to the star now in its place or the `h1`.
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'

import { api, ApiError, client, NETWORK_ERROR } from '@/api/client'
import type { components } from '@/api/schema'
import { focusHeading } from '@/app/routeFocus'
import { APPROVAL_DECISION, APPROVAL_REQUEST_STATUS } from '@/app/labels'
import Alert from '@/components/Alert.vue'
import Badge from '@/components/Badge.vue'
import ErrorState from '@/components/ErrorState.vue'
import PageHeader from '@/components/PageHeader.vue'
import SuccessStatus from '@/components/SuccessStatus.vue'
import { allows } from '@/composables/allowedActions'
import { ANNOUNCE_DELAY_MS, FORM_MESSAGES } from '@/composables/useFormErrors'
import { useLoad } from '@/composables/useLoad'
import ProjectList from '@/views/project/ProjectList.vue'

import FavoriteStar from './FavoriteStar.vue'
import MyWorkSection from './MyWorkSection.vue'
import WorkItemHeading from './WorkItemHeading.vue'

// A failed request is one error state for the page; a section the server couldn't read comes
// back unavailable and gets its own, so the other sections still show (TD-40). Failed loads in a
// row, of either kind, key those states, so a failed Try again is a new alert. Only one of them
// announces itself and takes focus: the one whose Try again was pressed, if it failed again,
// otherwise the first (UI-FBK-15).
type Section = 'favorites' | 'projects' | 'approvals' | 'decisions'
type Part = 'page' | Section
const PARTS: Part[] = ['page', 'favorites', 'projects', 'approvals', 'decisions']
const work = useLoad(() => api(client.GET('/api/me/work')))
const sections = computed(() => work.data.value?.sections)
const failedPart = (part: Part) =>
  part === 'page'
    ? Boolean(work.error.value)
    : !work.error.value && sections.value?.[part].available === false
const failed = computed(() => PARTS.some(failedPart))
const failures = ref(0)
const alerting = ref<Part>()

// A reload after a star keeps the content: it announces only the star's outcome, and if it
// fails, the page's error is the one alert, live at once (it follows the user's action).
const afterStar = ref(false)

async function load(pressed?: Part, star = false) {
  afterStar.value = star
  await work.run()
  failures.value = failed.value ? failures.value + 1 : 0
  alerting.value = pressed && failedPart(pressed) ? pressed : PARTS.find(failedPart)
}
onMounted(() => load())
const live = (part: Part) =>
  (failures.value > 1 || (afterStar.value && part === 'page')) && alerting.value === part

// Focus moves to the `h1` once everything has loaded: the Try again pressed is then gone.
async function retry(pressed: Part) {
  starFailure.value = ''
  await load(pressed)
  if (!failed.value) await focusHeading()
}

type MyProject = components['schemas']['MyProjectItem']
const starring = ref('')
const starred = ref('')
const starFailure = ref('')
const starFailures = ref(0)
const starAlert = ref<InstanceType<typeof Alert>>()
let lastStar: { list: string; index: number; id: string } | undefined

async function toggleStar(list: 'favorites' | 'projects', project: MyProject, index: number) {
  // One star change at a time, through its reload: a second press would send stale state.
  if (starring.value) return
  lastStar = { list, index, id: project.id }
  starring.value = project.id
  starFailure.value = ''
  starred.value = ''
  const path = { params: { path: { key: project.key } } }
  try {
    await api(
      project.is_favorite
        ? client.DELETE('/api/projects/{key}/favorite', path)
        : client.PUT('/api/projects/{key}/favorite', path),
    )
    starred.value = project.is_favorite
      ? `Removed ${project.name} from your favorites.`
      : `Added ${project.name} to your favorites.`
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    // A 403: the project was archived, or access lost, since the page loaded; the reload
    // takes the star away (DL-303).
    starFailure.value =
      error.status === 403
        ? `You don't have permission to change the star on ${project.name}.`
        : `Couldn't change the star on ${project.name}. ${
            error.code === NETWORK_ERROR ? FORM_MESSAGES.network : FORM_MESSAGES.generic
          }`
    starFailures.value += 1
  }
  // Pending until the reload ends, so a second press can't send the stale state again.
  await load(undefined, true)
  starring.value = ''
  await nextTick()
  if (work.error.value) return
  if (starFailure.value) starAlert.value?.focus()
  else await refocusStar()
}

// The star pressed if it's still listed; otherwise the one now in its row's place, or the `h1`.
async function refocusStar() {
  if (!lastStar) return
  const { list, index, id } = lastStar
  const stars = [...document.querySelectorAll<HTMLElement>(`[data-star^="${list}:"]`)]
  const target =
    stars.find((star) => star.dataset.star === `${list}:${id}`) ?? stars[index] ?? stars.at(-1)
  if (target) target.focus()
  else await focusHeading()
}

const said = ref('')
let announcing: ReturnType<typeof setTimeout> | undefined
onUnmounted(() => clearTimeout(announcing))

async function dismissStarFailure() {
  starFailure.value = ''
  clearTimeout(announcing)
  said.value = ''
  announcing = setTimeout(() => (said.value = 'Alert dismissed'), ANNOUNCE_DELAY_MS)
  await refocusStar()
}

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' })
const day = (at: string) => dateFormat.format(new Date(at))

const count = (n: number, one: string, many: string) => (n === 1 ? `1 ${one}` : `${n} ${many}`)
const announcement = computed(() => {
  if (afterStar.value) return ''
  if (work.loading.value) return 'Loading your work…'
  const { favorites, projects, approvals } = sections.value ?? {}
  return [
    // Said only when there are some: "0 favorite projects" on every load would be noise.
    favorites?.available &&
      favorites.total > 0 &&
      count(favorites.total, 'favorite project', 'favorite projects'),
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
      <SuccessStatus :message="starred" />
      <Alert
        v-if="starFailure"
        ref="starAlert"
        :key="starFailures"
        live
        dismissible
        @dismiss="dismissStarFailure"
        >{{ starFailure }}</Alert
      >
      <MyWorkSection
        id="favorites"
        heading="Favorite projects"
        thing="your favorite projects"
        empty-heading="No favorite projects"
        :section="sections?.favorites"
        :loading="work.loading.value"
        :failures="failures"
        :live="live('favorites')"
        @retry="retry('favorites')"
      >
        <template #empty>Star a project under Projects to keep it here, at the top.</template>
        <template #default="{ items, total }">
          <ProjectList :projects="items" with-access>
            <template #actions="{ project }">
              <FavoriteStar
                v-if="allows(project, 'project.favorite')"
                :data-star="`favorites:${project.id}`"
                :name="project.name"
                :favorite="project.is_favorite"
                :pending="starring === project.id"
                @toggle="toggleStar('favorites', project, items.indexOf(project))"
              />
            </template>
          </ProjectList>
          <p v-if="total > items.length" class="m-0 text-sm text-text-muted">
            Showing {{ items.length }} of {{ total }} favorite projects.
          </p>
        </template>
      </MyWorkSection>

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
          <ProjectList :projects="items" with-access>
            <template #actions="{ project }">
              <FavoriteStar
                v-if="allows(project, 'project.favorite')"
                :data-star="`projects:${project.id}`"
                :name="project.name"
                :favorite="project.is_favorite"
                :pending="starring === project.id"
                @toggle="toggleStar('projects', project, items.indexOf(project))"
              />
            </template>
          </ProjectList>
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
    <p class="sr-only" aria-live="polite">{{ said }}</p>
  </div>
</template>
