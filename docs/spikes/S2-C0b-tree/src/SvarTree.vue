<script setup lang="ts">
// SVAR DataGrid in tree mode, through the wrapper's two duties that matter here: every move goes
// to the server first (UI-SVR-5), and the move menu sits outside the widget (UI-SVR-6).
import { Grid, Willow } from '@svar-ui/vue-grid'
import { nextTick, ref } from 'vue'

import { checklist, locate, order, serverMove, startOpen, type Item } from './data'

const items = ref(checklist())
const message = ref('')
type Row = { id: number; number: string; title: string; status: string; open?: boolean; data?: Row[] }
// SVAR's move-item doesn't reorder in tree mode (grid-store 2.7.4 skips it when `tree` is set), so
// an allowed move re-renders from our data, keeping which branches are closed.
const closed = new Set<number>(startOpen ? [] : order(items.value))
const toRows = (xs: Item[]): Row[] =>
  xs.map(({ children, ...x }) =>
    children.length ? { ...x, open: !closed.has(x.id), data: toRows(children) } : x,
  )
const rows = ref(toRows(items.value))
const columns = [
  { id: 'title', header: 'Title', treetoggle: true, draggable: true, flexgrow: 1 },
  { id: 'number', header: 'ID', width: 100 },
  { id: 'status', header: 'Status', width: 120 },
]

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let api: any
const events: unknown[] = []

function applyToData(id: number, target: number, mode: string) {
  const from = locate(items.value, id)!
  const [moved] = from[0].splice(from[1], 1)
  const to = locate(items.value, target)!
  to[0].splice(mode === 'before' ? to[1] : to[1] + 1, 0, moved)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function init(a: any) {
  api = a
  api.on('open-row', (ev: { id: number }) => closed.delete(ev.id))
  api.on('close-row', (ev: { id: number }) => closed.add(ev.id))
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  api.intercept('move-item', (ev: any) => {
    events.push({ ...ev })
    if (ev.inProgress) return true // the drag preview; the drop is decided below
    const { id, target, mode } = ev
    serverMove(id, target, mode).then((ok) => {
      if (ok) {
        applyToData(id, target, mode)
        rows.value = toRows(items.value)
        // Focus follows the moved row (the menu is outside the widget).
        nextTick(() => api.exec('focus-cell', { row: id, column: 'title' }))
        message.value = ''
      } else {
        message.value = 'You can’t move this requirement.'
      }
    })
    return false
  })
}

function move(dir: 'up' | 'down') {
  const id = api.getState().selectedRows[0]
  if (id == null) return
  const [siblings, i] = locate(items.value, id)!
  const j = dir === 'up' ? i - 1 : i + 1
  if (j < 0 || j >= siblings.length) return
  api.exec('move-item', { id, target: siblings[j].id, mode: dir === 'up' ? 'before' : 'after' })
}

Object.assign(window, {
  spike: {
    dataOrder: () => order(items.value),
    screenOrder: () =>
      [...document.querySelectorAll('[role=row][data-id]')].map((r) => Number(r.getAttribute('data-id'))),
    storeOrder: () => api.getState().flatData.map((r: Row) => r.id),
    events,
    api: () => api,
  },
})
</script>

<template>
  <div class="mb-2 flex gap-2">
    <button type="button" class="rounded border px-2" data-move="up" @click="move('up')">Move up</button>
    <button type="button" class="rounded border px-2" data-move="down" @click="move('down')">Move down</button>
    <p role="status" class="text-sm">{{ message }}</p>
  </div>
  <div style="height: 600px">
    <Willow :fonts="false">
      <Grid :data="rows" :columns="columns" :tree="true" :reorder="true" :init="init" />
    </Willow>
  </div>
</template>
