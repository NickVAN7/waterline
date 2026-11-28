<script setup lang="ts">
// A menu button opening a popover of links (UI-SHL-4, UI-SHL-6): PrimeVue's Popover (UI-STY-3).
// Past FILTER_AFTER links, a Filter button shows a filter field and moves focus to it. Following a
// link closes it. Opening it moves focus inside (the current link, or the first): the popover sits
// at the end of `<body>`, so Tab from the button would never reach it. Esc returns to the button.
// With `search`, the filter is the caller's server search (the project selector, DL-422): the
// typed text goes out (`filter`) after the filter bar's delay, the field stays while it's in use,
// and the popover says when it shows fewer links than match (`total`).
import Popover from 'primevue/popover'
import { computed, nextTick, ref, watch } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

import { SEARCH_DELAY_MS } from '@/components/FilterBar.vue'
import Icon from '@/components/Icon.vue'

export type PopoverLink = { id: string; label: string; detail?: string; to: RouteLocationRaw }

const props = defineProps<{
  /** The popover's accessible name, and the filter's subject ("Projects"). */
  name: string
  links: PopoverLink[]
  currentId?: string
  /** The links are loading (the list is `aria-busy`). */
  busy?: boolean
  /** The button fills its container, the arrow at its end (the sidebar's project selector). */
  wide?: boolean
  /** The filter searches on the server: `filter` sends the text, `links` are what it found. */
  search?: boolean
  /** How many match, when that's more than `links` holds. */
  total?: number
}>()
const emit = defineEmits<{ open: []; filter: [term: string] }>()

const FILTER_AFTER = 8

const popover = ref<InstanceType<typeof Popover>>()
const button = ref<HTMLButtonElement>()
// For an action in the footer that opens a dialog: focus back on the button first, so the dialog
// returns focus there.
defineExpose({ focus: () => button.value?.focus() })
const expanded = ref(false)
const filter = ref('')
const filtering = ref(false)
const filterInput = ref<HTMLInputElement>()

async function startFilter() {
  filtering.value = true
  await nextTick()
  filterInput.value?.focus()
}
const popoverId = `popover-${props.name.toLowerCase().replace(/\W+/g, '-')}`

const shown = computed(() => {
  const term = filter.value.trim().toLowerCase()
  if (!term || props.search) return props.links
  return props.links.filter((link) =>
    `${link.label} ${link.detail ?? ''}`.toLowerCase().includes(term),
  )
})

const more = computed(() =>
  props.total !== undefined && props.total > props.links.length ? props.total : 0,
)

let searching: ReturnType<typeof setTimeout> | undefined
watch(filter, (term) => {
  // Closing empties the filter; the next open loads afresh.
  if (!props.search || !expanded.value) return
  clearTimeout(searching)
  searching = setTimeout(() => emit('filter', term.trim()), SEARCH_DELAY_MS)
})

function toggle(event: Event) {
  if (!expanded.value) emit('open')
  popover.value?.toggle(event)
}

// Focus goes in once the links are there: opened while they load, or reloading while open (Try
// again), it waits for them, so it never drops with the control that started the load.
let focusWhenLoaded = false
// The control that had focus when a reload started while open (the filter for a search, Try
// again): it keeps focus if it's still there once loaded (UI-FBK-15).
let heldAtReload: Element | null = null

async function focusInside() {
  await nextTick()
  const root = document.getElementById(popoverId)
  const held = heldAtReload
  heldAtReload = null
  if (held?.isConnected && document.activeElement === held) return
  const target =
    root?.querySelector<HTMLElement>('input') ??
    root?.querySelector<HTMLElement>('a[aria-current]') ??
    root?.querySelector<HTMLElement>('li a') ??
    root?.querySelector<HTMLElement>('a, button')
  target?.focus()
}

async function onShow() {
  expanded.value = true
  focusWhenLoaded = Boolean(props.busy)
  await focusInside()
}

watch(
  () => props.busy,
  (busy) => {
    if (!expanded.value) return
    if (busy) {
      focusWhenLoaded = true
      heldAtReload = document.activeElement
      return
    }
    if (!focusWhenLoaded) return
    focusWhenLoaded = false
    void focusInside()
  },
)

function onHide() {
  expanded.value = false
  clearTimeout(searching)
  filter.value = ''
  filtering.value = false
}
</script>

<template>
  <button
    ref="button"
    type="button"
    aria-haspopup="dialog"
    :aria-expanded="expanded ? 'true' : 'false'"
    :aria-controls="expanded ? popoverId : undefined"
    :class="[
      'inline-flex min-h-(--control-height) max-w-full items-center gap-2 rounded-md border border-border bg-bg px-3 text-left text-text hover:bg-hover',
      wide && 'w-full justify-between',
    ]"
    @click="toggle"
  >
    <span class="break-words"><slot name="button" /></span>
    <Icon name="chevron-down" />
  </button>
  <Popover
    :id="popoverId"
    ref="popover"
    :aria-label="name"
    :aria-describedby="$slots.header ? `${popoverId}-header` : undefined"
    @show="onShow"
    @hide="onHide"
  >
    <div class="flex w-72 max-w-full flex-col gap-2">
      <!-- The popover's description, read with its name: focus goes straight to a link. -->
      <div v-if="$slots.header" :id="`${popoverId}-header`"><slot name="header" /></div>
      <!-- Kept while filtering: a server search can find fewer than it takes to show the button. -->
      <template v-if="filtering || links.length > FILTER_AFTER || more">
        <div v-if="filtering" class="flex flex-col gap-1">
          <label :for="`${popoverId}-filter`" class="text-sm font-medium"
            >Filter {{ name.toLowerCase() }}</label
          >
          <input
            :id="`${popoverId}-filter`"
            ref="filterInput"
            v-model="filter"
            type="search"
            autocomplete="off"
            :aria-describedby="more ? `${popoverId}-more` : undefined"
            class="min-h-(--control-height) rounded-md border border-border bg-bg px-3 text-text"
          />
        </div>
        <button
          v-else
          type="button"
          class="inline-flex min-h-(--control-height) items-center gap-2 self-start rounded-md px-2 text-text-muted hover:bg-hover hover:text-text"
          @click="startFilter"
        >
          <Icon name="search" />Filter {{ name.toLowerCase() }}
        </button>
      </template>
      <ul
        :aria-busy="busy ? 'true' : 'false'"
        class="m-0 flex max-h-80 list-none flex-col overflow-y-auto p-0"
      >
        <li v-for="link in shown" :key="link.id">
          <RouterLink
            :to="link.to"
            :aria-current="link.id === currentId ? 'true' : undefined"
            class="flex min-h-(--control-height) flex-col justify-center rounded-md px-2 text-text no-underline hover:bg-hover"
            @click="popover?.hide()"
          >
            <span :class="link.id === currentId ? 'font-semibold' : ''">{{ link.label }}</span>
            <!-- So the name and detail aren't read as one word. -->
            {{ ' ' }}
            <span v-if="link.detail" class="font-mono text-sm text-text-muted">{{
              link.detail
            }}</span>
          </RouterLink>
        </li>
        <li v-if="!shown.length" class="px-2 py-1 text-text-muted">
          <slot name="empty">No {{ name.toLowerCase() }} match.</slot>
        </li>
      </ul>
      <p v-if="more && !busy" :id="`${popoverId}-more`" class="m-0 px-2 text-sm text-text-muted">
        Showing {{ links.length }} of {{ more }}. Filter to find the rest.
      </p>
      <slot name="footer" :close="() => popover?.hide()" />
    </div>
  </Popover>
</template>
