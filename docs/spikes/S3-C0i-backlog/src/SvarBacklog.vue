<script setup lang="ts">
// SVAR DataGrid, flat, with `reorder` on, through the wrapper's two duties (UI-SVR-5, UI-SVR-6):
// every move goes to the server first, and the move menu sits outside the widget. Our array is
// the source of truth; the grid is re-fed from it after the server answers.
import { Grid, Willow } from '@svar-ui/vue-grid'
import { nextTick, ref } from 'vue'

import { backlog, MESSAGE, moveTo, serverMove, target, type Direction } from './data'

// ?fix=1: the wrapper draws the drag handle itself. Willow's icons are an icon font from SVAR's
// CDN, which `:fonts="false"` (UI-SVR-3) and UI-STY-4 rule out, so the handle has no size.
const fix = new URLSearchParams(location.search).get('fix') === '1'
const items = ref(backlog())
const rows = ref(items.value.slice())
const message = ref('')
const columns = [
  { id: 'title', header: 'Title', draggable: true, flexgrow: 1 },
  { id: 'number', header: 'ID', width: 100 },
  { id: 'status', header: 'Status', width: 130 },
  { id: 'assignee', header: 'Assignee', width: 160 },
]

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let api: any
const events: string[] = []
let lastMode = 'after'

async function decide(id: number, to: number) {
  const ok = await serverMove(id, to)
  if (ok) moveTo(items.value, id, to)
  // Re-fed either way: an allowed move shows, a refused one snaps back to our order.
  rows.value = items.value.slice()
  message.value = ok ? '' : MESSAGE
  await nextTick()
  api.exec('select-row', { id })
  api.exec('focus-cell', { row: id, column: 'title' })
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function init(a: any) {
  api = a
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  api.intercept('move-item', (ev: any) => {
    events.push(`${ev.id} ${ev.mode} ${ev.target}${ev.inProgress ? ' (in progress)' : ''}`)
    // The drag's preview; the drop is decided below. The drop's own event carries no `mode`, so
    // the last preview's is kept.
    if (ev.inProgress) {
      lastMode = ev.mode
      return true
    }
    const mode = ev.mode ?? lastMode
    const index = items.value.findIndex((t) => t.id === ev.target)
    const from = items.value.findIndex((t) => t.id === ev.id)
    let to = mode === 'before' ? index : index + 1
    if (from < to) to -= 1
    void decide(ev.id, to)
    return false
  })
}

function move(dir: Direction) {
  const id = api.getState().selectedRows[0]
  if (id == null) return
  const from = items.value.findIndex((t) => t.id === id)
  const to = target(from, items.value.length, dir)
  if (to !== null) void decide(id, to)
}

Object.assign(window, {
  spike: {
    dataOrder: () => items.value.map((t) => t.id),
    screenOrder: () =>
      [...document.querySelectorAll('[role=row][data-id]')].map((r) => Number(r.getAttribute('data-id'))),
    events,
    api: () => api,
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
  <div style="height: 600px" :class="{ 'drawn-handle': fix }">
    <Willow :fonts="false">
      <Grid :data="rows" :columns="columns" :reorder="true" :init="init" />
    </Willow>
  </div>
</template>

<style>
.drawn-handle .wx-draggable {
  display: inline-block;
  width: 1rem;
  height: 1rem;
  margin-inline-end: 0.5rem;
  vertical-align: middle;
  cursor: grab;
  background-color: var(--color-text-muted);
  mask: url('/drag.svg') center / contain no-repeat;
}
</style>
