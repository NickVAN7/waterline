<script setup lang="ts">
// A menu button opening a popover of links (UI-SHL-4, UI-SHL-6): PrimeVue's Popover (UI-STY-3),
// with a filter field once there are more than FILTER_AFTER links. Following a link closes it.
// Opening it moves focus inside (the filter, the current link, or the first): the popover sits
// at the end of `<body>`, so Tab from the button would never reach it. Esc returns to the button.
import Popover from 'primevue/popover'
import { computed, nextTick, ref, watch } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

import Icon from '@/components/Icon.vue'

export type PopoverLink = { id: string; label: string; detail?: string; to: RouteLocationRaw }

const props = defineProps<{
  /** The popover's accessible name, and the filter's subject ("Projects"). */
  name: string
  links: PopoverLink[]
  currentId?: string
  /** The links are loading (the list is `aria-busy`). */
  busy?: boolean
}>()
const emit = defineEmits<{ open: [] }>()

const FILTER_AFTER = 8

const popover = ref<InstanceType<typeof Popover>>()
const button = ref<HTMLButtonElement>()
// For an action in the footer that opens a dialog: focus back on the button first, so the dialog
// returns focus there.
defineExpose({ focus: () => button.value?.focus() })
const expanded = ref(false)
const filter = ref('')
const popoverId = `popover-${props.name.toLowerCase().replace(/\W+/g, '-')}`

const shown = computed(() => {
  const term = filter.value.trim().toLowerCase()
  if (!term) return props.links
  return props.links.filter((link) =>
    `${link.label} ${link.detail ?? ''}`.toLowerCase().includes(term),
  )
})

function toggle(event: Event) {
  if (!expanded.value) emit('open')
  popover.value?.toggle(event)
}

// Focus goes in once the links are there: opened while they load, or reloading while open (Try
// again), it waits for them, so it never drops with the control that started the load.
let focusWhenLoaded = false

async function focusInside() {
  await nextTick()
  const root = document.getElementById(popoverId)
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
      return
    }
    if (!focusWhenLoaded) return
    focusWhenLoaded = false
    void focusInside()
  },
)

function onHide() {
  expanded.value = false
  filter.value = ''
}
</script>

<template>
  <button
    ref="button"
    type="button"
    aria-haspopup="dialog"
    :aria-expanded="expanded ? 'true' : 'false'"
    :aria-controls="expanded ? popoverId : undefined"
    class="inline-flex min-h-(--control-height) max-w-full items-center gap-2 rounded-md border border-border bg-bg px-3 text-left text-text hover:bg-hover"
    @click="toggle"
  >
    <span class="break-words"><slot name="button" /></span>
    <Icon name="chevron-down" />
  </button>
  <Popover :id="popoverId" ref="popover" :aria-label="name" @show="onShow" @hide="onHide">
    <div class="flex w-72 max-w-full flex-col gap-2">
      <div v-if="links.length > FILTER_AFTER" class="flex flex-col gap-1">
        <label :for="`${popoverId}-filter`" class="text-sm font-medium"
          >Filter {{ name.toLowerCase() }}</label
        >
        <input
          :id="`${popoverId}-filter`"
          v-model="filter"
          type="search"
          autocomplete="off"
          class="min-h-(--control-height) rounded-md border border-border bg-bg px-3 text-text"
        />
      </div>
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
      <slot name="footer" :close="() => popover?.hide()" />
    </div>
  </Popover>
</template>
