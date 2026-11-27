<script lang="ts">
// Typing settles before the list reloads (as UI-FRM-9's checks).
export const SEARCH_DELAY_MS = 300
</script>

<script setup lang="ts">
// A list's filter bar (DL-419, UI-TBL-10): a search field (`q`), an Add filter menu of the list's
// declared filters, a chip per filter in use (its button opens a popover with the operator and
// the values; a named remove button), Clear while a search or a filter is set, and the list's
// toggle last ("Show deactivated"; not a chip, since it widens the list; Clear leaves it alone,
// DL-420). One type size throughout, the form fields' (`--text-base`). It holds no state of its
// own beyond the typing and a filter just added: the URL does (`useListQuery`), so the host passes the
// current values and applies the `change` it emits (`query.filtered`). An enum filter is "any of"
// (`name`) or "none of" (`name__not`); other types join with their first lists (DL-419).
import Menu from 'primevue/menu'
import type { MenuItem } from 'primevue/menuitem'
import Popover from 'primevue/popover'
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

import Icon from './Icon.vue'

export type EnumFilter = {
  /** The parameter's name; "none of" is `<name>__not`. */
  name: string
  label: string
  options: { value: string; label: string }[]
}
export type FilterChanges = Record<string, string | string[]>

const props = defineProps<{
  /** The search field's label ("Search people"). */
  searchLabel: string
  search: string
  filters?: EnumFilter[]
  /** The repeated filters' values, by parameter (`role`, `role__not`). */
  values?: Record<string, string[]>
  /** The list's toggle, for those who may use it (its parameter is `'true'` when on). */
  toggle?: { name: string; label: string; checked: boolean }
}>()
const emit = defineEmits<{ change: [changes: FilterChanges] }>()

const id = useId()
const searchInput = ref<HTMLInputElement>()
const addButton = ref<HTMLButtonElement>()
const addMenu = ref<InstanceType<typeof Menu>>()
const adding = ref(false)
const popover = ref<InstanceType<typeof Popover>>()
const chipButtons = ref<Record<string, HTMLButtonElement | null>>({})

// --- Search ---------------------------------------------------------------------------------

const typed = ref(props.search)
// The URL echoes what the bar sent a moment later; only an outside change (Back, a link, Clear)
// rewrites the field, so a keystroke typed meanwhile is never lost.
let sent = props.search
watch(
  () => props.search,
  (search) => {
    if (search !== sent) typed.value = sent = search
  },
)
let timer: ReturnType<typeof setTimeout> | undefined
function onSearch() {
  clearTimeout(timer)
  timer = setTimeout(() => {
    const q = typed.value.trim()
    // Typed and undone: nothing changed, so the list keeps its page.
    if (q === sent) return
    sent = q
    emit('change', { q })
  }, SEARCH_DELAY_MS)
}
onBeforeUnmount(() => clearTimeout(timer))

// --- Chips ----------------------------------------------------------------------------------

const values = computed(() => props.values ?? {})
const filters = computed(() => props.filters ?? [])
const anyOf = (filter: EnumFilter) => values.value[filter.name] ?? []
const noneOf = (filter: EnumFilter) => values.value[`${filter.name}__not`] ?? []
const inUse = (filter: EnumFilter) => anyOf(filter).length + noneOf(filter).length > 0

// A filter picked from Add filter is a chip before it has a value; it goes if none is chosen.
const added = ref('')
const editing = ref<EnumFilter>()
// A chip being edited stays while its popover is open, even with its last value unticked: it goes
// on close, as a filter just added does (focus then moves to Add filter).
const chips = computed(() =>
  filters.value.filter((f) => inUse(f) || f.name === added.value || f.name === editing.value?.name),
)
const addable = computed(() => filters.value.filter((f) => !chips.value.includes(f)))

function chipText(filter: EnumFilter) {
  const none = noneOf(filter).length > 0
  const chosen = none ? noneOf(filter) : anyOf(filter)
  const labels = chosen.map((v) => filter.options.find((o) => o.value === v)?.label ?? v)
  if (!labels.length) return filter.label
  return `${filter.label}: ${none ? 'not ' : ''}${labels.join(', ')}`
}

const addItems = computed<MenuItem[]>(() =>
  addable.value.map((filter) => ({
    label: filter.label,
    command: () => void startFilter(filter),
  })),
)
function toggleAdd(event: Event) {
  addMenu.value?.toggle(event)
}

async function startFilter(filter: EnumFilter) {
  added.value = filter.name
  // Open once the click that picked it has finished: a browser runs microtasks between a click's
  // listeners, so a popover opened a tick later would see that click reach the document as one
  // outside it, and close at once (the owner, S3-C16).
  await new Promise((resolve) => setTimeout(resolve))
  open(filter)
}

// --- The popover: operator and values -------------------------------------------------------

const operator = ref<'any' | 'none'>('any')
const popoverId = `${id}-filter`

function open(filter: EnumFilter, event?: Event) {
  editing.value = filter
  operator.value = noneOf(filter).length ? 'none' : 'any'
  const target = chipButtons.value[filter.name]
  if (!target) return
  popover.value?.show(event ?? new Event('click'), target)
}

function chosen(filter: EnumFilter) {
  return operator.value === 'none' ? noneOf(filter) : anyOf(filter)
}

function apply(filter: EnumFilter, list: string[]) {
  const none = operator.value === 'none'
  emit('change', { [filter.name]: none ? [] : list, [`${filter.name}__not`]: none ? list : [] })
}

function onValue(filter: EnumFilter, value: string, event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const list = chosen(filter).filter((v) => v !== value)
  apply(filter, checked ? [...list, value] : list)
}

function onOperator(filter: EnumFilter, next: 'any' | 'none') {
  const list = chosen(filter)
  operator.value = next
  if (list.length) apply(filter, list)
}

async function onShow() {
  await nextTick()
  // The popover sits at the end of `<body>`: focus goes in, on the operator chosen (traps.md).
  document.getElementById(popoverId)?.querySelector<HTMLElement>('input:checked')?.focus()
}

async function onHide() {
  const filter = editing.value
  editing.value = undefined
  // Focus in the popover, dropped, or back on the chip (PrimeVue's Escape): it's ours to place.
  const active = document.activeElement
  const focusWasInside =
    active === document.body ||
    isInPopover() ||
    (!!filter && active === chipButtons.value[filter.name])
  if (filter && added.value === filter.name) added.value = ''
  await nextTick()
  if (!focusWasInside || !filter) return
  // Back to the chip; a chip left without a value has gone, so to Add filter.
  ;(chipButtons.value[filter.name] ?? addButton.value)?.focus()
}
function isInPopover() {
  return !!document.getElementById(popoverId)?.contains(document.activeElement)
}

// After a removal, focus goes to Add filter once it's there: the chip goes, and the button comes
// back, only when the host has passed the new values (after its URL change, not a tick later).
let focusAdd = false
watch(
  addButton,
  (button) => {
    if (button && focusAdd) {
      focusAdd = false
      button.focus()
    }
  },
  { flush: 'post' },
)

function remove(filter: EnumFilter) {
  if (added.value === filter.name) added.value = ''
  emit('change', { [filter.name]: [], [`${filter.name}__not`]: [] })
  if (addButton.value) addButton.value.focus()
  else focusAdd = true
}

// --- Clear and the toggle -------------------------------------------------------------------

// A search or a filter: Clear leaves the toggle alone, so it never hides people (DL-420).
const anything = computed(() => !!props.search || filters.value.some(inUse))

async function clear() {
  clearTimeout(timer)
  typed.value = sent = ''
  added.value = ''
  const changes: FilterChanges = { q: '' }
  for (const filter of filters.value) {
    changes[filter.name] = []
    changes[`${filter.name}__not`] = []
  }
  emit('change', changes)
  await nextTick()
  // Clear has gone with what it cleared.
  searchInput.value?.focus()
}

function onToggle(event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  emit('change', { [props.toggle!.name]: checked ? 'true' : '' })
}

// The list's empty state offers Clear filters through the bar (UI-FBK-8).
defineExpose({ clear })

// PrimeVue sets `aria-level`, which a menu item may not have (axe `aria-allowed-attr`).
const menuPt = { item: () => ({ 'aria-level': undefined }) }
</script>

<template>
  <div role="group" aria-label="Filters" class="flex flex-wrap items-center gap-2">
    <div class="flex items-center gap-2">
      <label :for="`${id}-search`" class="font-medium">{{ searchLabel }}</label>
      <input
        :id="`${id}-search`"
        ref="searchInput"
        v-model="typed"
        type="search"
        maxlength="200"
        autocomplete="off"
        class="min-h-(--control-height) w-48 max-w-full rounded-md border border-border bg-bg px-3 text-text"
        @input="onSearch"
      />
    </div>
    <template v-if="filters.length">
      <button
        v-if="addable.length"
        ref="addButton"
        type="button"
        aria-haspopup="menu"
        :aria-controls="adding ? `${id}-add` : undefined"
        :aria-expanded="adding ? 'true' : 'false'"
        class="inline-flex min-h-(--control-height) items-center gap-1 rounded-md border border-border bg-bg px-3 text-text hover:bg-hover"
        @click="toggleAdd"
      >
        Add filter<Icon name="chevron-down" />
      </button>
      <!-- On a page, never in a modal dialog: no fixed layer (MoreActionsMenu's) needed. -->
      <Menu
        :id="`${id}-add`"
        ref="addMenu"
        :model="addItems"
        popup
        aria-label="Add filter"
        :pt="menuPt"
        @show="adding = true"
        @hide="adding = false"
      />
      <span
        v-for="filter in chips"
        :key="filter.name"
        class="inline-flex max-w-full items-center rounded-md border border-border bg-bg"
      >
        <button
          :ref="(el) => (chipButtons[filter.name] = el as HTMLButtonElement | null)"
          type="button"
          aria-haspopup="dialog"
          :aria-expanded="editing === filter ? 'true' : 'false'"
          :aria-controls="editing === filter ? popoverId : undefined"
          class="inline-flex min-h-(--control-height) max-w-full items-center gap-1 rounded-l-md px-3 text-left text-text hover:bg-hover"
          @click="open(filter, $event)"
        >
          <span class="break-words">{{ chipText(filter) }}</span
          ><Icon name="chevron-down" />
        </button>
        <button
          type="button"
          :aria-label="`Remove ${filter.label} filter`"
          title="Remove"
          class="inline-flex size-(--control-height-sm) items-center justify-center rounded-r-md text-text-muted hover:bg-hover hover:text-text"
          @click="remove(filter)"
        >
          <Icon name="x" />
        </button>
      </span>
    </template>
    <button
      v-if="anything"
      type="button"
      class="inline-flex min-h-(--control-height) items-center rounded-md px-2 text-text-muted underline hover:text-text"
      @click="clear"
    >
      Clear
    </button>
    <label v-if="toggle" class="ml-auto flex items-center gap-2">
      <input
        :name="toggle.name"
        type="checkbox"
        class="size-(--target-min) shrink-0"
        :checked="toggle.checked"
        @change="onToggle"
      />
      <span>{{ toggle.label }}</span>
    </label>
    <Popover
      :id="popoverId"
      ref="popover"
      :aria-label="editing ? `${editing.label} filter` : 'Filter'"
      @show="onShow"
      @hide="onHide"
    >
      <div v-if="editing" class="flex w-64 max-w-full flex-col gap-3">
        <fieldset class="m-0 flex flex-col gap-1 border-0 p-0">
          <legend class="mb-1 font-medium">{{ editing.label }}</legend>
          <label class="flex items-center gap-2">
            <input
              type="radio"
              :name="`${id}-operator`"
              class="size-(--target-min) shrink-0"
              :checked="operator === 'any'"
              @change="onOperator(editing, 'any')"
            />
            <span>Is any of</span>
          </label>
          <label class="flex items-center gap-2">
            <input
              type="radio"
              :name="`${id}-operator`"
              class="size-(--target-min) shrink-0"
              :checked="operator === 'none'"
              @change="onOperator(editing, 'none')"
            />
            <span>Is none of</span>
          </label>
        </fieldset>
        <!-- A rule between the operator and the values (owner, S3-C16's report). -->
        <fieldset
          class="m-0 flex flex-col gap-1 border-x-0 border-t border-b-0 border-border-subtle p-0 pt-3"
        >
          <legend class="sr-only">{{ editing.label }} values</legend>
          <label
            v-for="option in editing.options"
            :key="option.value"
            class="flex items-center gap-2"
          >
            <input
              type="checkbox"
              class="size-(--target-min) shrink-0"
              :checked="chosen(editing).includes(option.value)"
              @change="onValue(editing, option.value, $event)"
            />
            <span>{{ option.label }}</span>
          </label>
        </fieldset>
      </div>
    </Popover>
  </div>
</template>
