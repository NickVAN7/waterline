<script setup lang="ts">
// PrimeVue TreeTable: our data drives it, so a move is the server's answer applied to our array.
import Column from 'primevue/column'
import TreeTable from 'primevue/treetable'
import { nextTick, ref } from 'vue'

import { checklist, locate, order, serverMove, startOpen, type Item } from './data'

const items = ref(checklist())
const message = ref('')
type Node = { key: string; data: Omit<Item, 'children'>; children: Node[] }
const toNodes = (xs: Item[]): Node[] =>
  xs.map(({ children, ...x }) => ({ key: String(x.id), data: x, children: toNodes(children) }))
// Built once; a move splices the same node objects, so only the moved rows re-render.
// ?rebuild=1 rebuilds every node instead, to measure the difference.
const rebuild = new URLSearchParams(location.search).get('rebuild') === '1'
const nodes = ref(toNodes(items.value))
const expandedKeys = ref<Record<string, boolean>>(
  startOpen ? Object.fromEntries(order(items.value).map((id) => [String(id), true])) : {},
)
const selectionKeys = ref<Record<string, boolean>>({})

// ?fix=1: the table gets its name, the toggle button (tabindex -1; the row carries aria-expanded)
// leaves the accessibility tree, and Right on a closed row only opens it (WAI treegrid).
const fix = new URLSearchParams(location.search).get('fix') === '1'
const tablePt = fix ? { table: { 'aria-label': 'Requirements' } } : {}
const togglePt = fix ? { nodeToggleButton: { 'aria-hidden': 'true' } } : {}
function onKeydown(event: KeyboardEvent) {
  const row = (event.target as HTMLElement).closest('tr[aria-expanded="false"]')
  if (!fix || event.code !== 'ArrowRight' || !row) return
  event.preventDefault()
  event.stopPropagation()
  row.querySelector<HTMLElement>('[data-pc-section="nodetogglebutton"]')?.click()
}

function locateNode(xs: Node[], key: string): Node[] | null {
  if (xs.some((x) => x.key === key)) return xs
  for (const x of xs) {
    const found = locateNode(x.children, key)
    if (found) return found
  }
  return null
}

async function move(dir: 'up' | 'down') {
  const key = Object.keys(selectionKeys.value)[0]
  if (!key) return
  const id = Number(key)
  const [siblings, i] = locate(items.value, id)!
  const j = dir === 'up' ? i - 1 : i + 1
  if (j < 0 || j >= siblings.length) return
  const ok = await serverMove(id, siblings[j].id, dir === 'up' ? 'before' : 'after')
  if (!ok) {
    message.value = 'You can’t move this requirement.'
    return
  }
  const [moved] = siblings.splice(i, 1)
  siblings.splice(j, 0, moved)
  if (rebuild) {
    nodes.value = toNodes(items.value)
  } else {
    const parent = locateNode(nodes.value, key)!
    const [movedNode] = parent.splice(i, 1)
    parent.splice(j, 0, movedNode)
  }
  message.value = ''
  // Focus follows the moved row (the menu is outside the widget).
  await nextTick()
  const rowOf = (n: number) =>
    [...document.querySelectorAll<HTMLElement>('tbody [role=row]')].find(
      (r) => r.querySelector('td:nth-child(2)')?.textContent === `RQ-${n}`,
    )
  rowOf(id)?.focus()
}

Object.assign(window, {
  spike: {
    dataOrder: () => order(items.value),
    screenOrder: () =>
      [...document.querySelectorAll('tbody [role=row]')].map((r) =>
        Number(r.querySelector('td:nth-child(2)')?.textContent?.replace('RQ-', '')),
      ),
  },
})
</script>

<template>
  <div class="mb-2 flex gap-2">
    <button type="button" class="rounded border px-2" data-move="up" @click="move('up')">Move up</button>
    <button type="button" class="rounded border px-2" data-move="down" @click="move('down')">Move down</button>
    <p role="status" class="text-sm">{{ message }}</p>
  </div>
  <TreeTable
    v-model:expanded-keys="expandedKeys"
    v-model:selection-keys="selectionKeys"
    :value="nodes"
    selection-mode="single"
    scrollable
    scroll-height="600px"
    aria-label="Requirements"
    :pt="tablePt"
    @keydown.capture="onKeydown"
  >
    <Column field="title" header="Title" expander :pt="togglePt" />
    <Column field="number" header="ID" />
    <Column field="status" header="Status" />
  </TreeTable>
</template>
