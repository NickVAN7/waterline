<script setup lang="ts">
// PrimeVue DataTable with row reorder: our array drives the table, so a move is the server's
// answer applied to it (UI-SVR-5), and the move menu sits outside the table (UI-SVR-6).
import Column from 'primevue/column'
import DataTable, { type DataTableRowReorderEvent } from 'primevue/datatable'
import { nextTick, ref } from 'vue'

import { backlog, MESSAGE, moveTo, serverMove, target, type Direction, type Task } from './data'

const items = ref(backlog())
const selection = ref<Task | null>(null)
const message = ref('')
const events: string[] = []
// ?virtual=1: the table's virtual scroller, so only the rows in view are drawn.
const virtual = new URLSearchParams(location.search).get('virtual') === '1'
// ?fix=1: the handle column's header gets a name (axe's empty-table-header).
const fix = new URLSearchParams(location.search).get('fix') === '1'

async function decide(id: number, to: number) {
  const ok = await serverMove(id, to)
  if (ok) moveTo(items.value, id, to)
  message.value = ok ? '' : MESSAGE
  // Focus follows the moved row (the menu is outside the table).
  await nextTick()
  rowFor(id)?.focus()
}

// The table hands over its reordered copy; the order changes only once the server allows it.
function onReorder(event: DataTableRowReorderEvent) {
  const moved = items.value[event.dragIndex]
  events.push(`${moved.id} ${event.dragIndex} -> ${event.dropIndex}`)
  void decide(moved.id, event.dropIndex)
}

function move(dir: Direction) {
  if (!selection.value) return
  const from = items.value.findIndex((t) => t.id === selection.value!.id)
  const to = target(from, items.value.length, dir)
  if (to !== null) void decide(selection.value.id, to)
}

// The table takes no attributes per row, so rows are found by their ID cell.
const rows = () => [...document.querySelectorAll<HTMLElement>('tbody tr')]
const idOf = (row: HTMLElement) => Number(row.children[2]?.textContent?.replace('TA-', ''))
const rowFor = (id: number) => rows().find((row) => idOf(row) === id)

Object.assign(window, {
  spike: {
    dataOrder: () => items.value.map((t) => t.id),
    screenOrder: () => rows().map(idOf),
    events,
  },
})
</script>

<template>
  <div class="flex flex-wrap items-center gap-2">
    <button type="button" class="rounded border px-2" data-move="top" @click="move('top')">Move to top</button>
    <button type="button" class="rounded border px-2" data-move="up" @click="move('up')">Move up</button>
    <button type="button" class="rounded border px-2" data-move="down" @click="move('down')">Move down</button>
    <button type="button" class="rounded border px-2" data-move="bottom" @click="move('bottom')">Move to bottom</button>
    <p role="status" class="m-0 text-sm">{{ message }}</p>
  </div>
  <DataTable
    v-model:selection="selection"
    :value="items"
    data-key="id"
    selection-mode="single"
    scrollable
    scroll-height="600px"
    :virtual-scroller-options="virtual ? { itemSize: 38 } : undefined"
    :pt="{ table: { 'aria-label': 'Backlog' } }"
    @row-reorder="onReorder"
  >
    <Column row-reorder header-style="width: 3rem">
      <template v-if="fix" #header><span class="sr-only">Reorder</span></template>
    </Column>
    <Column field="title" header="Title" />
    <Column field="number" header="ID" />
    <Column field="status" header="Status" />
    <Column field="assignee" header="Assignee" />
  </DataTable>
</template>
