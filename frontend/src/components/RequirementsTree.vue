<script setup lang="ts">
// The requirement tree (DL-174): PrimeVue TreeTable over the project's ranked list (`items`,
// siblings in rank order, nested here by `parent_id`), every branch closed at first (DL-175).
// It has no drag: `MoveToMenu`, outside the widget, moves the selected row, and the server
// decides each move before the screen changes, so a refused one leaves the tree as the data is
// (UI-SVR-5, UI-SVR-6, DL-243). A refusal tells the page (TD-85): `stale` (the tree is out of
// date: reload it) or `refused` (a 403: reload what the user may do).
import Column from 'primevue/column'
import TreeTable from 'primevue/treetable'
import { computed, nextTick, ref, watch } from 'vue'

import { ApiError, NETWORK_ERROR, api, client } from '@/api/client'
import type { components } from '@/api/schema'
import { requirementStatusBadge } from '@/app/labels'
import { focusHeading } from '@/app/routeFocus'

import Alert from './Alert.vue'
import Badge from './Badge.vue'
import Button from './Button.vue'
import MovePickerDialog from './MovePickerDialog.vue'
import MoveToMenu, { type MoveAction } from './MoveToMenu.vue'

type Item = components['schemas']['RequirementItem']
type Node = { key: string; data: Item; children: Node[] }
type Placement = components['schemas']['RequirementMove']

const props = defineProps<{ projectKey: string; items: Item[]; movable: boolean }>()
const emit = defineEmits<{ stale: []; refused: [] }>()

const displayId = (item: Item) => `${props.projectKey}-RQ-${item.number}`
const describe = (item: Item) => `${displayId(item)} ${item.title}`

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
const picker = ref<InstanceType<typeof MovePickerDialog>>()
const failureAlert = ref<InstanceType<typeof Alert>>()
const root = ref<HTMLElement>()
const expandedKeys = ref<Record<string, boolean>>({})
const selectionKeys = ref<Record<string, boolean>>({})
// The row focus is on: only its ID link is in the Tab order, so Tab leaves the tree after one
// link, not one per row (DL-266).
const focusedKey = ref<string | null>(null)
function onFocusin(event: FocusEvent) {
  const link = (event.target as HTMLElement)
    .closest('tr')
    ?.querySelector<HTMLElement>('[data-requirement-row]')
  if (link) focusedKey.value = link.dataset.requirementRow!
}
// A reload keeps the failure that caused it: the message says what happened.
watch(
  () => props.items,
  (items) => {
    nodes.value = nest(items)
    selectionKeys.value = {}
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

function everyNode(list: Node[]): Node[] {
  return list.flatMap((node) => [node, ...everyNode(node.children)])
}

const selected = computed(() => {
  const key = Object.keys(selectionKeys.value)[0]
  return key ? locate(nodes.value, key) : null
})

// A 404 or 422 means the tree on screen is out of date (the requirement, its neighbor, or its new
// parent moved or went); the 422's own message is the generic "The request is invalid."
// (UI-FBK-3). The page reloads the tree.
const STALE = "This requirement's place had changed, so the tree has been reloaded."
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

// The farthest sibling in a direction (the first or the last), or -1 when there's none.
function edgeOf(siblings: Node[], index: number, by: -1 | 1) {
  let edge = -1
  for (let at = neighborOf(siblings, index, by); at >= 0; at = neighborOf(siblings, at, by)) {
    edge = at
  }
  return edge
}

// The node's real siblings: those under the same parent, itself left out.
const siblingsOf = (siblings: Node[], node: Node) =>
  siblings.filter((other) => other !== node && other.data.parent_id === node.data.parent_id)

/** Sends the move; once the server agrees, `place` puts the node, taken out of its list, back. */
async function send(node: Node, body: Placement, place: (node: Node) => void) {
  pending.value = true
  try {
    await api(
      client.POST('/api/projects/{key}/requirements/{number}/move', {
        params: { path: { key: props.projectKey, number: node.data.number } },
        body,
      }),
    )
  } catch (error) {
    if (!(error instanceof ApiError)) throw error
    failure.value = messageFor(error)
    failures.value += 1
    if (error.status === 403) emit('refused')
    else if (error.status === 404 || error.status === 422) emit('stale')
    return
  } finally {
    pending.value = false
  }
  failure.value = ''
  const [siblings, index] = locate(nodes.value, node.key)!
  siblings.splice(index, 1)
  place(node)
  await reveal(node)
}

// Opens the moved row's branches, then puts focus on it: the menu that moved it sits outside the
// widget.
async function reveal(node: Node) {
  const ancestors: Record<string, boolean> = {}
  for (let id = node.data.parent_id; id;) {
    ancestors[id] = true
    const found = locate(nodes.value, id)
    id = found ? found[0][found[1]]!.data.parent_id : null
  }
  expandedKeys.value = { ...expandedKeys.value, ...ancestors }
  await nextTick()
  root.value
    ?.querySelector<HTMLElement>(`[data-requirement-row="${node.key}"]`)
    ?.closest('tr')
    ?.focus()
}

/** Selects a row, opens its branches, and focuses it (a requirement just created, DL-255);
 * false when it isn't in the tree (past the 2,000-row cap). */
async function show(id: string): Promise<boolean> {
  const found = locate(nodes.value, id)
  if (!found) return false
  const node = found[0][found[1]]!
  selectionKeys.value = { [node.key]: true }
  await reveal(node)
  return true
}

defineExpose({ show })

function step(by: -1 | 1) {
  const [siblings, index] = selected.value!
  const node = siblings[index]!
  const neighbor = siblings[neighborOf(siblings, index, by)]!
  const body = by < 0 ? { before_id: neighbor.data.id } : { after_id: neighbor.data.id }
  return send(node, { parent_id: node.data.parent_id, ...body }, (moved) => {
    const at = siblings.indexOf(neighbor)
    siblings.splice(by < 0 ? at : at + 1, 0, moved)
  })
}

function toEdge(by: -1 | 1) {
  const [siblings, index] = selected.value!
  const node = siblings[index]!
  const edge = siblings[edgeOf(siblings, index, by)]!
  // To the top, before the first sibling; to the bottom, no neighbor: the server puts it last.
  const body = by < 0 ? { before_id: edge.data.id } : {}
  return send(node, { parent_id: node.data.parent_id, ...body }, (moved) => {
    const at = siblings.indexOf(edge)
    siblings.splice(by < 0 ? at : at + 1, 0, moved)
  })
}

let picked: (value: string) => void = () => {}

function moveAfter() {
  const [siblings, index] = selected.value!
  const node = siblings[index]!
  picked = (id) => {
    const after = siblings.find((other) => other.key === id)!
    void send(node, { parent_id: node.data.parent_id, after_id: id }, (moved) => {
      siblings.splice(siblings.indexOf(after) + 1, 0, moved)
    })
  }
  void picker.value?.open({
    title: `Move ${displayId(node.data)} after…`,
    label: 'Place it after',
    options: siblingsOf(siblings, node).map((other) => ({
      value: other.key,
      label: describe(other.data),
    })),
  })
}

const TOP_LEVEL = ''

// Where Move to… may put it: not its own branch (the server refuses a cycle all the same,
// design-doc §6), nor where it already is, which is Move to bottom.
function placesFor(node: Node) {
  const own = new Set(everyNode([node]).map((n) => n.key))
  return [
    ...(node.data.parent_id ? [{ value: TOP_LEVEL, label: 'Top level (no parent)' }] : []),
    ...everyNode(nodes.value)
      .filter((other) => !own.has(other.key) && other.key !== node.data.parent_id)
      .map((other) => ({ value: other.key, label: describe(other.data) })),
  ]
}

function moveTo() {
  const [siblings, index] = selected.value!
  const node = siblings[index]!
  picked = (value) => {
    const parentId = value === TOP_LEVEL ? null : value
    void send(node, { parent_id: parentId }, (moved) => {
      moved.data = { ...moved.data, parent_id: parentId }
      const parent = parentId ? locate(nodes.value, parentId) : null
      ;(parent ? parent[0][parent[1]]!.children : nodes.value).push(moved)
    })
  }
  void picker.value?.open({
    title: `Move ${displayId(node.data)} to…`,
    label: 'New parent',
    options: placesFor(node),
  })
}

const actions = computed<MoveAction[]>(() => {
  const [siblings, index] = selected.value ?? [[], 0]
  const node = siblings[index]
  // Only a row with a parent can sit at the top level: its parent is past the cap.
  const orphan = Boolean(node?.data.parent_id) && siblings === nodes.value
  const reason = (by: -1 | 1, edge: string) =>
    neighborOf(siblings, index, by) >= 0 ? undefined : orphan ? "its parent isn't shown" : edge
  return [
    { label: 'Move to top', run: () => toEdge(-1), blockedReason: reason(-1, 'already first') },
    { label: 'Move up', run: () => step(-1), blockedReason: reason(-1, 'already first') },
    { label: 'Move down', run: () => step(1), blockedReason: reason(1, 'already last') },
    { label: 'Move to bottom', run: () => toEdge(1), blockedReason: reason(1, 'already last') },
    {
      label: 'Move after…',
      run: moveAfter,
      blockedReason:
        node && siblingsOf(siblings, node).length > 0
          ? undefined
          : orphan
            ? "its parent isn't shown"
            : 'no other requirement at this level',
    },
    {
      label: 'Move to…',
      run: moveTo,
      blockedReason: node && placesFor(node).length === 0 ? 'nowhere else to put it' : undefined,
    },
  ]
})

// The menu goes when a reload after a 403 takes the right to move away: the failure stays, and
// focus, if it was on the menu, goes to it.
watch(
  () => props.movable,
  async (movable) => {
    if (movable) return
    await nextTick()
    if (document.activeElement === document.body) failureAlert.value?.focus()
  },
)

function dismiss() {
  failure.value = ''
  if (props.movable) moveMenu.value?.focus()
  else void focusHeading()
}

// Expand all (DL-175): the second level at once, then the deeper branches a batch per frame, so
// drawing up to 2,000 rows never holds the page up for long.
const EXPAND_BATCH = 25
const expanding = ref(false)

async function expandAll() {
  expanding.value = true
  const open = (list: Node[]) =>
    Object.fromEntries(list.filter((n) => n.children.length).map((n) => [n.key, true]))
  expandedKeys.value = { ...expandedKeys.value, ...open(nodes.value) }
  const deeper = nodes.value.flatMap((node) => everyNode(node.children))
  const branches = deeper.filter((node) => node.children.length)
  for (let at = 0; at < branches.length; at += EXPAND_BATCH) {
    await new Promise(requestAnimationFrame)
    expandedKeys.value = { ...expandedKeys.value, ...open(branches.slice(at, at + EXPAND_BATCH)) }
  }
  expanding.value = false
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
    <div class="flex flex-wrap items-center gap-3">
      <Button variant="secondary" :pending="expanding" pending-label="Expanding…" @click="expandAll"
        >Expand all</Button
      >
      <MoveToMenu
        v-if="movable"
        ref="moveMenu"
        :name="selected ? displayId(selected[0][selected[1]]!.data) : null"
        :actions="actions"
        blocked-reason="Select a requirement to move it."
        :pending="pending"
      />
    </div>
    <Alert v-if="failure" ref="failureAlert" :key="failures" live dismissible @dismiss="dismiss">{{
      failure
    }}</Alert>
    <MovePickerDialog
      ref="picker"
      :fallback-focus="() => moveMenu?.focus()"
      @chosen="(value: string) => picked(value)"
    />
    <TreeTable
      v-model:expanded-keys="expandedKeys"
      v-model:selection-keys="selectionKeys"
      :value="nodes"
      selection-mode="single"
      :pt="{ ...tablePt, ...rowPt }"
      @keydown.capture="onKeydown"
      @focusin="onFocusin"
    >
      <Column field="title" header="Title" expander :pt="{ ...columnPt, ...headerPt }" />
      <Column header="ID" :pt="headerPt">
        <template #body="{ node }">
          <!-- The ID opens the requirement; a click elsewhere on the row selects it (DL-264), and
               only the focused row's link is a Tab stop (DL-266). The
               cells are memoized: TreeTable redraws every row on each Expand all frame, and a
               component with slot content would re-render each time (DL-253's pass mark). -->
          <RouterLink
            v-memo="[node.data.number, focusedKey === node.key]"
            :to="{ name: 'project-requirement', params: { number: node.data.number } }"
            :data-requirement-row="node.key"
            :tabindex="focusedKey === node.key ? undefined : -1"
            class="font-mono"
            >{{ displayId(node.data) }}</RouterLink
          >
        </template>
      </Column>
      <Column header="Status" :pt="headerPt">
        <template #body="{ node }">
          <!-- The status badge (DL-148, DL-252), memoized as the ID cell is. -->
          <Badge
            v-memo="[
              node.data.status,
              node.data.approved_revision_id,
              node.data.current_revision_id,
            ]"
            :tone="requirementStatusBadge(node.data).tone"
            :icon="requirementStatusBadge(node.data).icon"
            >{{ requirementStatusBadge(node.data).label }}</Badge
          >
        </template>
      </Column>
    </TreeTable>
  </div>
</template>
