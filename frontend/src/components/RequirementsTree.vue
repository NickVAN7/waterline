<script setup lang="ts">
// The requirement tree (DL-174): PrimeVue TreeTable over the project's ranked list (`items`,
// siblings in rank order, nested here by `parent_id`), every branch closed at first (DL-175).
// It has no drag: `MoveToMenu`, outside the widget, moves the selected row, and the server
// decides each move before the screen changes, so a refused one leaves the tree as the data is
// (UI-SVR-5, UI-SVR-6, DL-243).
import Column from 'primevue/column'
import TreeTable from 'primevue/treetable'
import { computed, nextTick, ref, watch } from 'vue'

import { ApiError, NETWORK_ERROR, api, client } from '@/api/client'
import type { components } from '@/api/schema'

import Alert from './Alert.vue'
import MoveToMenu, { type MoveAction } from './MoveToMenu.vue'

type Item = components['schemas']['RequirementItem']
type Node = { key: string; data: Item; children: Node[] }

const props = defineProps<{ projectKey: string; items: Item[]; movable: boolean }>()

const displayId = (item: Item) => `${props.projectKey}-RQ-${item.number}`

function nest(items: Item[]): Node[] {
  const nodes = new Map(items.map((item) => [item.id, { key: item.id, data: item, children: [] }]))
  const top: Node[] = []
  for (const node of nodes.values()) {
    // A parent past the 2,000-row cap (DL-159) isn't in the list: its child shows at the top.
    const parent = node.data.parent_id ? nodes.get(node.data.parent_id) : undefined
    ;(parent ? parent.children : top).push(node)
  }
  return top
}

// Built once per load; a move splices these same node objects, so only the moved rows redraw
// (the spike: 0.06 s at the cap, against 0.92 s rebuilding every node).
const nodes = ref<Node[]>([])
const pending = ref(false)
const failure = ref('')
const failures = ref(0)
const moveMenu = ref<InstanceType<typeof MoveToMenu>>()
const root = ref<HTMLElement>()
const expandedKeys = ref<Record<string, boolean>>({})
const selectionKeys = ref<Record<string, boolean>>({})
watch(
  () => props.items,
  (items) => {
    nodes.value = nest(items)
    selectionKeys.value = {}
    failure.value = ''
  },
  { immediate: true },
)

function locate(siblings: Node[], key: string): [Node[], number] | null {
  const index = siblings.findIndex((node) => node.key === key)
  if (index >= 0) return [siblings, index]
  for (const node of siblings) {
    const found = locate(node.children, key)
    if (found) return found
  }
  return null
}

const selected = computed(() => {
  const key = Object.keys(selectionKeys.value)[0]
  return key ? locate(nodes.value, key) : null
})

// A 404 or 422 here means the tree on screen is out of date (the requirement or its neighbor
// moved or went); the 422's own message is the generic "The request is invalid." (UI-FBK-3).
const STALE = "This requirement's place has changed. Reload the page to see the current tree."
const MESSAGES: Record<number, string> = {
  403: "You don't have permission to move this requirement.",
  404: STALE,
  422: STALE,
}
function messageFor(error: ApiError) {
  if (MESSAGES[error.status]) return MESSAGES[error.status]!
  if (error.code === NETWORK_ERROR) {
    return "Couldn't move the requirement. Check your connection and try again."
  }
  return "Couldn't move the requirement. Try again in a moment."
}

// The nearest sibling in a direction, or -1: a row shown at the top because its parent is past
// the cap (DL-159) has another parent, so a move steps over it.
function neighborOf(siblings: Node[], index: number, by: -1 | 1) {
  let at = index + by
  while (siblings[at] && siblings[at]!.data.parent_id !== siblings[index]!.data.parent_id) at += by
  return siblings[at] ? at : -1
}

async function move(by: -1 | 1) {
  if (!selected.value) return
  const [siblings, index] = selected.value
  const node = siblings[index]!
  const at = neighborOf(siblings, index, by)
  const neighbor = siblings[at]!
  pending.value = true
  try {
    await api(
      client.POST('/api/projects/{key}/requirements/{number}/move', {
        params: { path: { key: props.projectKey, number: node.data.number } },
        body: {
          parent_id: node.data.parent_id,
          ...(by < 0 ? { before_id: neighbor.data.id } : { after_id: neighbor.data.id }),
        },
      }),
    )
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    failure.value = messageFor(error)
    failures.value += 1
    return
  } finally {
    pending.value = false
  }
  failure.value = ''
  siblings.splice(index, 1)
  // Up, before the neighbor; down, after it, one place back once the row is out.
  siblings.splice(at, 0, node)
  // Focus follows the moved row: the menu that moved it sits outside the widget.
  await nextTick()
  root.value
    ?.querySelector<HTMLElement>(`[data-requirement-row="${node.key}"]`)
    ?.closest('tr')
    ?.focus()
}

const actions = computed<MoveAction[]>(() => {
  const [siblings, index] = selected.value ?? [[], 0]
  const node = siblings[index]
  // Only a row with a parent can sit at the top level: its parent is past the cap.
  const orphan = Boolean(node?.data.parent_id) && siblings === nodes.value
  const reason = (by: -1 | 1, edge: string) =>
    neighborOf(siblings, index, by) >= 0 ? undefined : orphan ? "its parent isn't shown" : edge
  return [
    {
      label: 'Move up',
      run: () => move(-1),
      blockedReason: reason(-1, 'already first'),
    },
    {
      label: 'Move down',
      run: () => move(1),
      blockedReason: reason(1, 'already last'),
    },
  ]
})

function dismiss() {
  failure.value = ''
  moveMenu.value?.focus()
}

// Right on a closed row only opens it (WAI treegrid): TreeTable also moves focus to the next row.
function onKeydown(event: KeyboardEvent) {
  const row = (event.target as HTMLElement).closest('tr[aria-expanded="false"]')
  if (event.code !== 'ArrowRight' || !row) return
  event.preventDefault()
  event.stopPropagation()
  row.querySelector<HTMLElement>('[data-pc-section="nodetogglebutton"]')?.click()
}

// The table's name lands on the outer `div` unless set on the table itself, and the expand
// button (`tabindex="-1"`; the row carries `aria-expanded`) leaves the accessibility tree.
const tablePt = { table: { 'aria-label': 'Requirements' } }
const columnPt = { nodeToggleButton: { 'aria-hidden': 'true' } }
// A selected row also gets the leading bar, not color alone (UI-TOK-9), on its first cell: the
// table's borders are separate, where a `tr`'s border isn't drawn. Only the selected row has one,
// since forced colors would draw a transparent border.
const rowPt = {
  row: ({ context }: { context: { selected: boolean } }) => ({
    class: context.selected ? ['*:first:border-l-3', '*:first:border-accent'] : undefined,
  }),
}
const headerPt = { headerCell: { scope: 'col' } }
</script>

<template>
  <div ref="root" class="flex flex-col gap-3">
    <template v-if="movable">
      <MoveToMenu
        ref="moveMenu"
        :name="selected ? displayId(selected[0][selected[1]]!.data) : null"
        :actions="actions"
        blocked-reason="Select a requirement to move it."
        :pending="pending"
      />
      <Alert v-if="failure" :key="failures" live dismissible @dismiss="dismiss">{{
        failure
      }}</Alert>
    </template>
    <TreeTable
      v-model:expanded-keys="expandedKeys"
      v-model:selection-keys="selectionKeys"
      :value="nodes"
      selection-mode="single"
      :pt="{ ...tablePt, ...rowPt }"
      @keydown.capture="onKeydown"
    >
      <Column field="title" header="Title" expander :pt="{ ...columnPt, ...headerPt }" />
      <Column header="ID" :pt="headerPt">
        <template #body="{ node }">
          <span :data-requirement-row="node.key">{{ displayId(node.data) }}</span>
        </template>
      </Column>
    </TreeTable>
  </div>
</template>
